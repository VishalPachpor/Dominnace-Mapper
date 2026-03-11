import logging
from app.services.execution_engine import ExecutionEngine
from app.database.db import SessionLocal
from app.models.user import User
from app.utils.telegram import send_telegram_message

logger = logging.getLogger(__name__)

class TradeManager:

    def __init__(self):
        self.engine = ExecutionEngine()

    async def process_signal(self, signal):

        symbol = signal.get("symbol")
        action = (signal.get("action") or signal.get("side", "")).lower()
        price = float(signal.get("price", 0))
        # We will receive dom_high and dom_low from the new webhook format
        dom_high_str = signal.get("dom_high")
        dom_low_str = signal.get("dom_low")
        
        # New Feature: Filter strictly for DOM signals to avoid over-trading on minor UP/DOWN signals
        signal_type = str(signal.get("signal_type", "")).upper()
        if signal_type != "DOM":
            logger.info(f"Skipping minor momentum signal ({signal_type}) for {symbol}. Only processing DOM signals.")
            return

        if dom_high_str and dom_low_str:
            dom_high = float(dom_high_str)
            dom_low = float(dom_low_str)
            dom_length = dom_high - dom_low
        else:
            # Do not calculate fake stops. Rely on risk management or manual closure.
            dom_length = 0

        trade = self.create_trade(symbol, action, price, dom_length)

        db = SessionLocal()
        try:
            active_users = db.query(User).filter(User.is_active == True).all()
            for user in active_users:
                try:
                    # Skip fake/test accounts safely
                    meta_id = getattr(user, "meta_account_id", None)
                    if meta_id and isinstance(meta_id, str) and meta_id.startswith("mt5-"):
                        logger.warning(f"Skipping test user {user.id} with fake account id: {meta_id}")
                        continue

                    logger.info(f"TradeManager processing signal: Action={action}, Symbol={symbol}, Entry={trade['entry']} for user {user.id}")
                    response = await self.engine.open_trade(user, trade)
                    
                    if response:
                        # MetaApi typically returns orderId and positionId
                        # Create the tracking record for the DB
                        from app.services.position_tracker import PositionTracker
                        tracker = PositionTracker()
                        
                        trade_data = {
                            "id": response.get("positionId") or response.get("orderId") or "mock_id",
                            "user_id": user.id,
                            "symbol": trade["symbol"],
                            "side": trade["side"],
                            "entry": trade["entry"],
                            "sl": trade["sl"],
                            "tp": trade["tp"],
                            "be_trigger": trade["be_trigger"],
                            "status": response.get("status", "OPEN")
                        }
                        tracker.save_position(trade_data)
                        logger.info(f"Position saved to db for user {user.id}")
                        
                        # Send Telegram Alert
                        alert_msg = (
                            f"🟢 <b>NEW TRADE EXECUTED</b>\n\n"
                            f"<b>Symbol:</b> {trade['symbol']}\n"
                            f"<b>Side:</b> {trade['side'].upper()}\n"
                            f"<b>Entry:</b> {trade['entry']}\n"
                            f"<b>Account:</b> {user.id[:8]}..."
                        )
                        await send_telegram_message(alert_msg)
                    else:
                        # Trade was skipped or rejected by the engine (e.g. no EA token)
                        logger.warning(f"Trade skipped for user {user.id} (no response from engine)")
                        alert_msg = (
                             f"⚠️ <b>SIGNAL RECEIVED BUT SKIPPED</b>\n\n"
                             f"<b>Symbol:</b> {trade['symbol']}\n"
                             f"<b>Reason:</b> Your MT5 Expert Advisor is not connected or Account not set.\n"
                             f"<b>Account:</b> {user.id[:8]}..."
                        )
                        await send_telegram_message(alert_msg)

                except Exception as e:
                    logger.error(f"Failed to execute trade for user {user.id}: {e}")
                    error_msg = f"🔴 <b>TRADE FAILED</b>\n\n<b>Symbol:</b> {symbol}\n<b>Error:</b> {e}"
                    await send_telegram_message(error_msg)
        except Exception as e:
            logger.error(f"Error processing signal for users: {e}")
        finally:
            db.close()

    def create_trade(self, symbol, action, price, dom_length):
        
        # Remove exchange prefix if present (e.g., BINANCE:BTCUSDT -> BTCUSDT)
        if ":" in symbol:
            symbol = symbol.split(":")[-1]

        # Normalize symbol for MT5 brokers (e.g. BTCUSDT -> BTCUSD)
        if symbol.endswith("USDT"):
            symbol = symbol[:-1]

        entry = price
        if dom_length > 0:
            if action == "buy":
                sl = price - dom_length
                tp = price + dom_length
                be_trigger = entry + (dom_length * 0.35)
            else:
                sl = price + dom_length
                tp = price - dom_length
                be_trigger = entry - (dom_length * 0.35)
        else:
            sl, tp, be_trigger = 0, 0, 0

        return {
            "symbol": symbol,
            "side": action,
            "entry": entry,
            "sl": sl,
            "tp": tp,
            "be_trigger": be_trigger
        }
