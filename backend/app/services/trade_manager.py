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
        
        # New Bot Context
        user_id = signal.get("user_id")
        bot_id = signal.get("bot_id")
        
        # We will receive dom_high and dom_low from the new webhook format
        dom_high_str = signal.get("dom_high")
        dom_low_str = signal.get("dom_low")
        
        # New Feature: Filter strictly for DOM signals to avoid over-trading on minor UP/DOWN signals
        signal_type = str(signal.get("signal_type", "")).upper()
        if signal_type != "DOM" and not bot_id:
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
        
        # Merge volume constraints natively
        if signal.get("custom_lot_size"):
            trade["volume"] = float(signal.get("custom_lot_size"))
        elif signal.get("max_bot_lot_size"):
            trade["volume"] = float(signal.get("max_bot_lot_size"))
        elif "volume" in signal:
            trade["volume"] = float(signal.get("volume"))

        db = SessionLocal()
        
        import time
        start_time = time.time()
        success_count = 0
        failure_count = 0
        skipped_count = 0
        
        try:
            # ★ CRITICAL SCALING FIX ★
            # Do NOT loop over all active users inside the worker.
            # The Signal Router already fanned-out jobs specific to user_id. 
            if user_id:
                active_users = db.query(User).filter(User.id == user_id, User.is_active == True).all()
            else:
                # Fallback for old unconverted TradingView signals
                logger.warning("Worker received signal without explicit user_id. Falling back to all users loop.")
                active_users = db.query(User).filter(User.is_active == True).all()

            for user in active_users:
                try:
                    # Skip fake/test accounts safely
                    meta_id = getattr(user, "meta_account_id", None)
                    if meta_id and isinstance(meta_id, str) and meta_id.startswith("mt5-"):
                        logger.warning(f"Skipping test user {user.id} with fake account id: {meta_id}")
                        skipped_count += 1
                        continue

                    logger.info(f"TradeManager processing signal: Action={action}, Symbol={symbol}, Entry={trade['entry']} for user {user.id}")
                    
                    # ── Critical Protection: Max Trades Per Day Guard ──
                    from app.utils.redis_client import redis_client
                    import datetime
                    
                    MAX_TRADES_PER_DAY = 20
                    today_str = datetime.datetime.utcnow().strftime("%Y-%m-%d")
                    daily_limit_key = f"daily_trades:{user.id}:{today_str}"
                    
                    current_trades = redis_client.get(daily_limit_key)
                    if current_trades and int(current_trades) >= MAX_TRADES_PER_DAY:
                        logger.warning(f"User {user.id} has reached the absolute MAX_TRADES_PER_DAY limit ({MAX_TRADES_PER_DAY}). Trade skipped to prevent unbounded drawdown.")
                        skipped_count += 1
                        continue
                        
                    # ── Phase 4 Protection: Centralized Risk Guards ──
                    from app.services.risk_guard import RiskGuardService, RiskGuardException
                    try:
                        await RiskGuardService.check_all_guards(user.id, user.meta_account_id, symbol)
                    except RiskGuardException as rge:
                        logger.warning(f"TradeManager: Risk Guard triggered for {user.id}. Reason: {rge.reason}")
                        
                        # Auto-pause user if broker disconnected or drawdown exceeded
                        if rge.reason in ["broker_disconnected", "drawdown_exceeded", "metaapi_error"]:
                            user.trading_paused = True
                            db.commit()
                            logger.info(f"User {user.id} trading automatically paused due to {rge.reason}.")
                            alert_msg = f"🔴 <b>TRADING PAUSED</b>\n\n<b>Account:</b> {user.id[:8]}\n<b>Reason:</b> {rge.message}\nAction required. Please check your dashboard."
                            await send_telegram_message(alert_msg)
                        skipped_count += 1
                        continue
                        
                    # Execute
                    response = await self.engine.open_trade(user, trade)
                    
                    if response:
                        from app.utils.metrics import successful_trades_total
                        successful_trades_total.labels(symbol=trade["symbol"]).inc()

                        # Increment successful trades count
                        redis_client.incr(daily_limit_key)
                        if not current_trades:
                            redis_client.expire(daily_limit_key, 86400) # Expiry in 24 hours
                        
                        # MetaApi typically returns orderId and positionId
                        # Create the tracking record for the DB
                        from app.services.position_tracker import PositionTracker
                        tracker = PositionTracker()
                        
                        trade_data = {
                            "id": response.get("positionId") or response.get("orderId") or str(__import__("uuid").uuid4()),
                            "user_id": user.id,
                            "bot_id": bot_id, # Track bot attribution
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
                        success_count += 1
                    else:
                        from app.utils.metrics import execution_failures_total
                        execution_failures_total.labels(reason="no_response_from_engine").inc()

                        # Trade was skipped or rejected by the engine (e.g. no EA token)
                        logger.warning(f"Trade skipped for user {user.id} (no response from engine)")
                        failure_count += 1

                except Exception as e:
                    import sentry_sdk
                    from app.utils.metrics import execution_failures_total
                    sentry_sdk.capture_exception(e)
                    execution_failures_total.labels(reason="trade_execution_exception").inc()

                    logger.error(f"Failed to execute trade for user {user.id}: {e}")
                    failure_count += 1

            # --- Telegram Aggregation ---
            total_processed = success_count + failure_count + skipped_count
            if total_processed > 0 and success_count > 0:
                elapsed = round(time.time() - start_time, 2)
                summary_msg = (
                    f"📊 <b>Signal Processed</b>\n\n"
                    f"<b>Symbol:</b> {symbol}\n"
                    f"<b>Side:</b> {action.upper()}\n"
                    f"<b>Executed:</b> {success_count}\n"
                    f"<b>Skipped/Failed:</b> {failure_count + skipped_count}\n"
                    f"<b>Latency:</b> {elapsed}s"
                )
                await send_telegram_message(summary_msg)

        except Exception as e:
            import sentry_sdk
            sentry_sdk.capture_exception(e)
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
