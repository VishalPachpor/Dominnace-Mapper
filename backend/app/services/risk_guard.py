import logging
from datetime import datetime
from app.utils.redis_client import redis_client
from app.services.metaapi_service import get_open_positions, get_account_information
from app.utils.metrics import risk_guard_triggers_total

logger = logging.getLogger(__name__)

# Configurable Limits
MAX_OPEN_POSITIONS = 5
MAX_POSITIONS_PER_SYMBOL = 1
MAX_DAILY_DRAWDOWN = 0.05 # 5%
MAX_SIGNALS_PER_MINUTE = 3

class RiskGuardException(Exception):
    def __init__(self, reason, message):
        self.reason = reason
        self.message = message
        risk_guard_triggers_total.labels(type=reason).inc()
        super().__init__(self.message)

class RiskGuardService:
    @staticmethod
    async def check_all_guards(user_id: str, account_id: str, symbol: str):
        """
        Runs all pre-execution risk checks.
        Raises RiskGuardException if any threshold is breached.
        """
        # 1. Signal Rate Limit Guard (Max 3 per minute)
        rate_key = f"user_signal_rate:{user_id}"
        signals = redis_client.incr(rate_key)
        if signals == 1:
            redis_client.expire(rate_key, 60)
        
        if signals > MAX_SIGNALS_PER_MINUTE:
            logger.warning(f"TRADE_REJECTED reason=signal_rate_limit user={user_id} symbol={symbol} (signals={signals}/min)")
            raise RiskGuardException("signal_rate_limit", "Maximum signal rate exceeded (3 per minute).")

        # 2. Broker Connection Guard (Cached)
        if not account_id:
            logger.warning(f"TRADE_REJECTED reason=broker_disconnected user={user_id} symbol={symbol} (no meta_account_id)")
            raise RiskGuardException("broker_disconnected", "No MetaApi account linked to user.")
            
        mt_status = redis_client.get(f"mt_status:{account_id}")
        if mt_status and isinstance(mt_status, bytes):
            mt_status = mt_status.decode("utf-8")
            
        if not mt_status:
            # Fallback to live query if cache missed or poller hasn't run yet
            from app.services.metaapi_service import get_account_status
            mt_status = await get_account_status(account_id)
            if mt_status:
                redis_client.setex(f"mt_status:{account_id}", 30, mt_status)
                
        if mt_status not in ["CONNECTED", "DEPLOYED"]:
            logger.warning(f"TRADE_REJECTED reason=broker_disconnected user={user_id} symbol={symbol} (status={mt_status})")
            raise RiskGuardException("broker_disconnected", "Broker MT5 terminal is not connected.")

        # 3. Max Concurrent Positions & Symbol Stack Guard
        # Fetch open positions from MetaApi
        try:
            positions = await get_open_positions(account_id)
        except Exception as e:
            import sentry_sdk
            sentry_sdk.capture_exception(e)
            logger.error(f"Error fetching open positions for {account_id}: {e}")
            raise RiskGuardException("metaapi_error", "Could not fetch open positions to verify risk.")

        pos_count = len(positions)
        if pos_count >= MAX_OPEN_POSITIONS:
            logger.warning(f"TRADE_REJECTED reason=max_positions user={user_id} symbol={symbol} (open={pos_count})")
            raise RiskGuardException("max_positions_reached", f"Maximum open positions ({MAX_OPEN_POSITIONS}) reached.")

        # Symbol lock
        symbol_count = sum(1 for p in positions if p.get("symbol", "").upper().startswith(symbol.upper()))
        if symbol_count >= MAX_POSITIONS_PER_SYMBOL:
            logger.warning(f"TRADE_REJECTED reason=symbol_already_open user={user_id} symbol={symbol}")
            raise RiskGuardException("symbol_already_open", f"Maximum positions for {symbol} ({MAX_POSITIONS_PER_SYMBOL}) reached.")

        # 4. Daily Drawdown Guard (Equity based)
        try:
            account_info = await get_account_information(account_id)
            equity = account_info.get("equity", 0)
            balance = account_info.get("balance", 0)
        except Exception as e:
            import sentry_sdk
            sentry_sdk.capture_exception(e)
            logger.error(f"Error fetching account info for {account_id}: {e}")
            raise RiskGuardException("metaapi_error", "Could not fetch account equity to verify drawdown.")
            
        today_str = datetime.utcnow().strftime("%Y-%m-%d")
        start_balance_key = f"start_balance:{account_id}:{today_str}"
        
        # Initialize start balance for today if not present
        start_balance = redis_client.get(start_balance_key)
        if not start_balance:
            # If this is the first check of the day, lock in the current balance
            start_balance = balance
            # Store in Redis with an expiry of ~24 hours (86400 seconds)
            redis_client.setex(start_balance_key, 86400, str(start_balance))
        else:
            start_balance = float(start_balance)
            
        if start_balance > 0:
            drawdown = (start_balance - equity) / start_balance
            if drawdown >= MAX_DAILY_DRAWDOWN:
                logger.warning(f"TRADE_REJECTED reason=drawdown_exceeded user={user_id} symbol={symbol} (drawdown={drawdown:.2%})")
                raise RiskGuardException("drawdown_exceeded", f"Daily drawdown limit ({MAX_DAILY_DRAWDOWN*100}%) reached.")

        return True
