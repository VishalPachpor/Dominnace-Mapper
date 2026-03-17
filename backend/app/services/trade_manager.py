import logging
from app.services.execution_engine import ExecutionEngine
from app.services.execution_adapter import adapt_order
from app.services.exceptions import ExecutionValidationError, BrokerAdapterError
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
        dom_high = None
        dom_low = None
        
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

        trade = self.create_trade(symbol, action, price, dom_length, dom_high, dom_low)
        
        # Merge volume constraints natively
        if signal.get("custom_lot_size"):
            trade["volume"] = float(signal.get("custom_lot_size"))
        elif signal.get("max_bot_lot_size"):
            trade["volume"] = float(signal.get("max_bot_lot_size"))
        elif "volume" in signal:
            trade["volume"] = float(signal.get("volume"))

        db = SessionLocal()
        signal_id = signal.get("signal_id")
        from app.models.signal import Signal
        if signal_id:
            signal_exists = db.query(Signal.id).filter(Signal.id == signal_id).first()
            if not signal_exists:
                signal_id = None

        if not signal_id:
            signal_time_str = signal.get("signal_time")
            signal_time = None
            if signal_time_str:
                from datetime import datetime, timedelta, timezone
                try:
                    signal_time = datetime.fromisoformat(signal_time_str.replace("Z", "+00:00"))
                    if signal_time.tzinfo is None:
                        signal_time = signal_time.replace(tzinfo=timezone.utc)
                except Exception:
                    signal_time = None

            signal_query = db.query(Signal.id).filter(
                Signal.bot_id == bot_id,
                Signal.symbol == symbol,
                Signal.direction == action.upper(),
            )
            if signal_time:
                from datetime import timedelta
                window_start = signal_time - timedelta(minutes=5)
                window_end = signal_time + timedelta(minutes=5)
                signal_query = signal_query.filter(
                    Signal.signal_time >= window_start,
                    Signal.signal_time <= window_end,
                )

            resolved_signal = signal_query.order_by(Signal.created_at.desc()).first()
            if resolved_signal:
                signal_id = resolved_signal.id
                logger.info(
                    f"Resolved missing signal_id for {symbol} via signal lookup: {signal_id}"
                )

        if not signal_id:
            logger.warning(f"Skipping execution: missing or unknown signal_id for {symbol}. Enforcing webhook-only trades.")
            db.close()
            return
        
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
                        
                    # ── Execution Adapter: Broker-aware normalization ──
                    # Runs BEFORE any MetaApi call. Normalizes symbol, volume, SL/TP
                    # and price precision for this specific broker account.
                    adapted_order = None
                    try:
                        if user.meta_account_id:
                            adapted_order = await adapt_order(signal, user.meta_account_id)
                            # Merge adapted values back into trade dict so engine uses them
                            trade["symbol"]  = adapted_order.get("symbol", trade["symbol"])
                            trade["volume"]  = adapted_order.get("volume", trade.get("volume"))
                            trade["sl"]      = adapted_order.get("sl", trade.get("sl"))
                            trade["tp"]      = adapted_order.get("tp", trade.get("tp"))
                            if adapted_order.get("_stops_adjusted"):
                                logger.info(f"[Adapter] Stops auto-adjusted for broker compliance on account {user.meta_account_id}")
                    except ExecutionValidationError as eva:
                        from app.utils.metrics import execution_failures_total
                        execution_failures_total.labels(reason=eva.code).inc()
                        logger.warning(f"[Adapter] PRE_VALIDATION failed for user {user.id}: {eva}")
                        # Log the failure to DB so it shows in the UI
                        from app.models.trade import Trade
                        from datetime import datetime, timezone
                        import uuid
                        db.add(Trade(
                            id=str(uuid.uuid4()),
                            user_id=user.id,
                            signal_id=signal_id,
                            bot_id=bot_id,
                            symbol=trade["symbol"],
                            side=trade["side"],
                            entry=trade["entry"],
                            lot_size=trade.get("volume"),
                            execution_time=datetime.now(timezone.utc),
                            status="EXECUTION_FAILED",
                            result="FAILED",
                            reject_reason=str(eva),
                        ))
                        db.commit()
                        failure_count += 1
                        continue
                    except BrokerAdapterError as bae:
                        logger.warning(f"[Adapter] Broker spec unavailable for {user.id}: {bae}. Proceeding with raw signal.")
                        # Non-fatal: continue with original trade dict (broker will reject if invalid)

                    # Execute
                    response = await self.engine.open_trade(user, trade)
                    
                    # ── SAFE Mode Broker Retry ──
                    # Some brokers report stopLevel=0 but still reject the order with INVALID_STOPS.
                    meta_result = response.get("result", {}) if response else {}
                    if response:
                        string_code = meta_result.get("stringCode")
                        from app.services.execution_adapter import EXECUTION_MODE
                        if (
                            string_code == "TRADE_RETCODE_INVALID_STOPS"
                            and EXECUTION_MODE == "SAFE"
                            and (trade.get("sl") is not None or trade.get("tp") is not None)
                        ):
                            logger.warning(f"[TradeManager] Broker rejected with INVALID_STOPS. SAFE mode active: retrying without stops for {user.id}")
                            trade["sl"] = None
                            trade["tp"] = None
                            trade["_execution_note"] = "Stops removed during broker retry due to TRADE_RETCODE_INVALID_STOPS"
                            response = await self.engine.open_trade(user, trade)

                    if not response:
                        from app.utils.metrics import execution_failures_total
                        execution_failures_total.labels(reason="no_response_from_engine").inc()
                        logger.warning(f"Trade skipped for user {user.id} (no response from engine)")
                        failure_count += 1
                        continue

                    engine_status = response.get("status")
                    
                    # ── Evaluate True Execution Success ──
                    is_execute_success = False
                    meta_result = {}
                    pos_id = None
                    reject_reason = response.get("reason") or engine_status
                    
                    if engine_status == "success":
                        meta_result = response.get("result", {})
                        string_code = meta_result.get("stringCode", "UNKNOWN")
                        pos_id = meta_result.get("positionId") or meta_result.get("orderId")
                        
                        # 10009 = DONE, 10008 = PLACED
                        if string_code in ["TRADE_RETCODE_DONE", "TRADE_RETCODE_PLACED"] and pos_id:
                            is_execute_success = True
                        else:
                            reject_reason = f"Broker Rejected: {string_code} - {meta_result.get('message', 'No details')}"

                    elif engine_status == "rejected":
                        meta_result = response.get("result", {})
                        string_code = meta_result.get("stringCode")
                        if string_code:
                            reject_reason = f"Broker Rejected: {string_code} - {meta_result.get('message', 'No details')}"

                    if is_execute_success:
                        from app.utils.metrics import successful_trades_total
                        successful_trades_total.labels(symbol=trade["symbol"]).inc()

                        # Increment successful trades count
                        redis_client.incr(daily_limit_key)
                        if not current_trades:
                            redis_client.expire(daily_limit_key, 86400) # Expiry in 24 hours
                        
                        # --- NEW: Immediate Trade Logging (Execution Flow) ---
                        from app.models.trade import Trade
                        from datetime import datetime, timezone

                        signal_time_str = signal.get("signal_time")
                        signal_time = None
                        if signal_time_str:
                            try:
                                signal_time = datetime.fromisoformat(signal_time_str)
                            except Exception:
                                pass
                                
                        execution_time_str = meta_result.get("time_done") or meta_result.get("time") 
                        if execution_time_str:
                            try:
                                execution_time = datetime.fromisoformat(execution_time_str.replace("Z", "+00:00"))
                            except Exception:
                                execution_time = datetime.now(timezone.utc)
                        else:
                            execution_time = datetime.now(timezone.utc)

                        latency_ms = None
                        if signal_time:
                            latency_ms = int((execution_time - signal_time).total_seconds() * 1000)

                        new_trade = Trade(
                            id=pos_id,
                            user_id=user.id,
                            signal_id=signal_id,
                            bot_id=bot_id,
                            symbol=trade["symbol"],
                            side=trade["side"],
                            entry=trade["entry"],
                            lot_size=trade.get("volume"),
                            execution_time=execution_time,
                            execution_latency_ms=latency_ms,
                            status="EXECUTED",
                            result="OPEN",
                            metaapi_trade_id=pos_id
                        )
                        db.add(new_trade)

                        # Create the tracking record for the DB
                        from app.services.position_tracker import PositionTracker
                        tracker = PositionTracker()
                        
                        trade_data = {
                            "id": pos_id,
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
                        
                        # Persistent state for Reversal/BE logic (Advanced engine)
                        from app.models.trade_state import TradeState
                        ts = TradeState(
                            user_id=user.id,
                            symbol=trade["symbol"],
                            position_id=pos_id, # Direct link to position record
                            bot_slug=signal.get("strategy_slug", "unknown"),
                            entry_price=trade["entry"],
                            sl_price=trade["sl"],
                            tp_price=trade["tp"],
                            be_trigger=trade["be_trigger"],
                            side=trade["side"],
                            status="OPEN"
                        )
                        db.add(ts)
                        db.commit()
                        
                        logger.info(f"Position, Trade(EXECUTED) and TradeState saved to db for user {user.id}")
                        success_count += 1
                    else:
                        from app.utils.metrics import execution_failures_total
                        execution_failures_total.labels(reason="rejected_or_skipped").inc()

                        logger.warning(f"Trade Execution FAILED for user {user.id}. Reason: {reject_reason}")
                        
                        # Log EXECUTION_FAILED to DB so user can see what happened
                        from app.models.trade import Trade
                        from datetime import datetime, timezone
                        
                        failed_id = str(__import__("uuid").uuid4())
                        new_trade = Trade(
                            id=failed_id,
                            user_id=user.id,
                            signal_id=signal_id,
                            bot_id=bot_id,
                            symbol=trade["symbol"],
                            side=trade["side"],
                            entry=trade["entry"],
                            lot_size=trade.get("volume"),
                            execution_time=datetime.now(timezone.utc),
                            execution_latency_ms=None,
                            status="EXECUTION_FAILED",
                            result="FAILED",
                            metaapi_trade_id=None,
                            reject_reason=reject_reason
                        )
                        db.add(new_trade)
                        db.commit()
                        
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

    def create_trade(self, symbol, action, price, dom_length, dom_high=None, dom_low=None):
        """
        Build a trade dict using the correct DOM SL/TP model.

        BUY:
            SL = dom_low                        (price must close below the DOM zone to invalidate)
            TP = dom_high + dom_length          (project equal distance above the zone)
            BE = entry + (dom_length * 0.35)    (move SL to breakeven at 35% of target)

        SELL:
            SL = dom_high
            TP = dom_low - dom_length
            BE = entry - (dom_length * 0.35)
        """
        # Remove exchange prefix if present (e.g., BINANCE:BTCUSDT -> BTCUSDT)
        if ":" in symbol:
            symbol = symbol.split(":")[-1]

        # Normalize symbol for MT5 brokers (e.g. BTCUSDT -> BTCUSD)
        if symbol.endswith("USDT"):
            symbol = symbol[:-1]

        entry = price

        if dom_high is not None and dom_low is not None and dom_high > dom_low:
            # ── CORRECT DOM RULE ──────────────────────────────────────────────
            dom_length = dom_high - dom_low
            if action == "buy":
                sl = dom_low                          # SL at bottom of DOM zone
                tp = dom_high + dom_length            # TP = zone top + full zone range
                be_trigger = entry + (dom_length * 0.35)
            else:  # sell
                sl = dom_high                         # SL at top of DOM zone
                tp = dom_low - dom_length             # TP = zone bottom - full zone range
                be_trigger = entry - (dom_length * 0.35)

        elif dom_length > 0:
            # ── Fallback: old signals without explicit dom_high/dom_low ──────
            # Keep previous behaviour so old webhook format still works
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
            "sl": round(sl, 5) if sl else 0,
            "tp": round(tp, 5) if tp else 0,
            "be_trigger": round(be_trigger, 5) if be_trigger else 0,
        }
