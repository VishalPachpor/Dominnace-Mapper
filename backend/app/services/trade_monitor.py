import logging
import asyncio
from datetime import datetime, timezone
from collections import defaultdict
from app.database.db import SessionLocal
from app.models.trade_state import TradeState
from app.models.trade import Trade
from app.models.position import Position
from app.models.user import User
from app.services.execution_engine import ExecutionEngine
from app.services.trade_manager import TradeManager
from app.services.analytics import AnalyticsService
from app.services.trade_closer import force_close_orphaned_trades_for_user

logger = logging.getLogger(__name__)

# Profit-protection ladder tuned for BTC/crypto so winners are not clipped
# too early by a tiny breakeven buffer.
BE_TRIGGER_RATIO = 0.50
BE_BUFFER_RATIO = 0.05


def _original_dom_entry(state: TradeState) -> float:
    dom_close = state.dom_close
    if dom_close is not None:
        return float(dom_close)
    return float(state.entry_price)


def _original_dom_stop(state: TradeState) -> float:
    if state.side == "buy":
        if state.dom_low is not None:
            return float(state.dom_low)
    else:
        if state.dom_high is not None:
            return float(state.dom_high)
    return float(state.sl_price)


def _original_dom_risk(state: TradeState) -> float:
    return abs(_original_dom_entry(state) - _original_dom_stop(state))


def _deal_reason_text(close_deal: dict) -> str:
    return " ".join(
        str(close_deal.get(key) or "").upper()
        for key in ("reason", "comment")
    ).strip()


def _closed_by_stop_loss(close_deal: dict, state: TradeState, preclose_status: str) -> bool:
    reason_text = _deal_reason_text(close_deal)
    if "DEAL_REASON_SL" in reason_text or reason_text == "SL":
        return True

    # If the trade had already moved to BE, a stop-based exit should not trigger
    # a reversal. We only reverse the original DOM invalidation stop.
    if preclose_status == "BE_MOVED":
        return False

    try:
        exit_price = float(close_deal.get("price", 0) or 0)
    except Exception:
        return False

    stop_price = _original_dom_stop(state)
    dom_length = float(state.dom_length or 0.0)
    tolerance = max(dom_length * 0.05, 0.5)
    return stop_price > 0 and abs(exit_price - stop_price) <= tolerance

class TradeMonitorService:
    def __init__(self):
        self.engine = ExecutionEngine()
        self.manager = TradeManager()

    async def monitor_all_trades(self):
        db = SessionLocal()
        try:
            active_states = db.query(TradeState).filter(
                TradeState.status.in_(["OPEN", "BE_MOVED", "CLOSING"])
            ).all()

            for state in active_states:
                try:
                    await self._process_state(db, state)
                except Exception as e:
                    logger.error(f"Error processing TradeState {state.id}: {e}")

            await self._reconcile_closed_mismatches(db)
            db.commit()
        finally:
            db.close()

    async def _process_state(self, db, state: TradeState):
        user = db.query(User).filter(User.id == state.user_id).first()
        if not user:
            return

        if not getattr(user, "can_trade", True):
            closed_count = force_close_orphaned_trades_for_user(
                db, user.id, close_reason="ACCOUNT_INACTIVE"
            )
            if closed_count:
                logger.warning(
                    f"Force-closed {closed_count} orphaned trade(s) for inactive user {user.id}"
                )
            db.commit()
            return

        if not user.meta_account_id:
            return

        # 1. Check if position still exists on MetaApi
        try:
            positions = await self.engine.get_positions(user.meta_account_id)
            # Guard against positions dicts missing 'symbol' (e.g. pending orders from MetaApi)
            if state.position_id:
                matching_pos = next(
                    (p for p in positions if str(p.get("id")) == str(state.position_id)),
                    None
                )
            else:
                matching_pos = next(
                    (p for p in positions
                     if p.get("symbol") == state.symbol and (p.get("type") or "").lower() == state.side.lower()),
                    None
                )
            
            if not matching_pos:
                # Position is closed. Check if it was a loss for reversal.
                await self._handle_closed_position(db, state, user)
                return

            # 2. Position is OPEN. Check for Breakeven trigger.
            trade_record = None
            if state.position_id:
                trade_record = db.query(Trade).filter(Trade.id == state.position_id).first()
            if trade_record:
                trade_record.last_synced_at = datetime.now(timezone.utc)
                if trade_record.status == "CLOSING":
                    trade_record.status = "OPEN"
                    trade_record.result = "OPEN"

            state.last_checked_at = datetime.now(timezone.utc)
            if state.status == "CLOSING":
                state.status = "OPEN"

            if state.status == "OPEN":
                current_price = float(matching_pos["currentPrice"])
                triggered = False
                if state.side == "buy" and current_price >= state.be_trigger:
                    triggered = True
                elif state.side == "sell" and current_price <= state.be_trigger:
                    triggered = True
                
                if triggered:
                    dom_length = float(state.dom_length or 0.0)
                    if dom_length <= 0 and state.be_trigger != state.entry_price:
                        dom_length = abs(state.be_trigger - state.entry_price) / BE_TRIGGER_RATIO
                    be_buffer = dom_length * BE_BUFFER_RATIO
                    protected_sl = state.entry_price + be_buffer if state.side == "buy" else state.entry_price - be_buffer
                    logger.info(
                        f"BE Triggered for {state.id} ({state.symbol}). "
                        f"Moving SL to {protected_sl}"
                    )
                    success = await self.engine.update_position_sl(user, matching_pos["id"], protected_sl)
                    if success:
                        state.status = "BE_MOVED"
                        state.sl_price = protected_sl
            db.commit()

        except Exception as e:
            logger.error(f"Failed to fetch/process MetaApi state for {state.user_id}: {e}")

    async def _handle_closed_position(self, db, state: TradeState, user: User):
        """
        Handles a closed position. If it closed at SL and is a DOM trade, trigger reversal.
        """
        logger.info(f"Trade {state.id} ({state.symbol}) detected as CLOSED.")

        # Idempotency guard: if trade row is already closed with exit data,
        # do not re-apply close bookkeeping (avoids duplicate metrics/events).
        existing_trade = db.query(Trade).filter(Trade.id == state.position_id).first() if state.position_id else None
        if existing_trade and existing_trade.status == "CLOSED" and existing_trade.exit is not None:
            if state.status != "REVERSED":
                state.status = "CLOSED"
            state.last_checked_at = datetime.now(timezone.utc)
            db.commit()
            return

        # Check history to see if it was a Loss (SL hit)
        deals = await self.engine.get_deals(user.meta_account_id, days=7)
        last_deal = next(
            (d for d in deals
             if d.get("entryType") == "DEAL_ENTRY_OUT"
             and str(d.get("positionId")) == str(state.position_id)),
            None,
        )

        if not last_deal:
            # MetaApi may lag; don't mark closed until we see a closing deal
            logger.warning(
                f"Position {state.position_id} not found in open positions, but no closing deal yet. "
                f"Deferring close sync for {state.symbol}."
            )
            if state.position_id:
                trade_record = db.query(Trade).filter(Trade.id == state.position_id).first()
                if trade_record:
                    trade_record.retry_count = int(trade_record.retry_count or 0) + 1
                    trade_record.last_synced_at = datetime.now(timezone.utc)
            state.status = "CLOSING"
            state.last_checked_at = datetime.now(timezone.utc)
            db.commit()
            return

        preclose_status = state.status

        # Mark as CLOSING before final atomic close update.
        state.status = "CLOSING"
        state.last_checked_at = datetime.now(timezone.utc)
        trade_record = db.query(Trade).filter(Trade.id == state.position_id).first() if state.position_id else None
        if trade_record:
            trade_record.status = "CLOSING"
            trade_record.last_synced_at = datetime.now(timezone.utc)
        db.commit()

        exit_price = float(last_deal.get("price", 0))
        pnl = (
            float(last_deal.get("profit", 0) or 0)
            + float(last_deal.get("swap", 0) or 0)
            + float(last_deal.get("commission", 0) or 0)
        )
        is_loss = pnl < 0
        closed_at = None
        deal_time = last_deal.get("time")
        if deal_time:
            try:
                closed_at = datetime.fromisoformat(deal_time.replace("Z", "+00:00"))
            except Exception:
                closed_at = datetime.now(timezone.utc)
        if not closed_at:
            closed_at = datetime.now(timezone.utc)

        # Atomic close sync for Trade + Position + TradeState only.
        # Analytics is best-effort and must never roll back the close itself.
        try:
            pos = db.query(Position).filter(Position.id == state.position_id).first() if state.position_id else None
            trade_record = db.query(Trade).filter(Trade.id == state.position_id).first() if state.position_id else None

            if pos:
                pos.status = "CLOSED"
                pos.exit_price = exit_price
                pos.pnl = pnl
                pos.closed_at = closed_at
                logger.info(f"Synced exit data for Position {pos.id} (Price: {exit_price}, PnL: {pnl})")

            if trade_record:
                trade_record.status = "CLOSED"
                trade_record.result = "WIN" if pnl > 0 else ("LOSS" if pnl < 0 else "BE")
                trade_record.close_time = closed_at
                trade_record.exit = exit_price
                trade_record.pnl = pnl
                trade_record.last_synced_at = datetime.now(timezone.utc)
                trade_record.retry_count = 0
                logger.info(f"Synced exit data for Trade(CLOSED) {trade_record.id}")

            state.status = "CLOSED"
            state.last_checked_at = datetime.now(timezone.utc)
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"Atomic close sync failed for {state.position_id}: {e}")
            state.status = "CLOSING"
            state.last_checked_at = datetime.now(timezone.utc)
            trade_record = db.query(Trade).filter(Trade.id == state.position_id).first() if state.position_id else None
            if trade_record:
                trade_record.status = "CLOSING"
                trade_record.retry_count = int(trade_record.retry_count or 0) + 1
                trade_record.last_synced_at = datetime.now(timezone.utc)
            db.commit()
            return

        try:
            AnalyticsService.update_trade_metrics(db, state.bot_slug, pnl, autocommit=True)
        except Exception as e:
            logger.error(f"Analytics update skipped for closed trade {state.position_id}: {e}")

        closed_by_sl = _closed_by_stop_loss(last_deal, state, preclose_status)

        if is_loss and closed_by_sl and preclose_status != "BE_MOVED" and not state.reversal_used:
            # TRIGGER REVERSAL — only for DOM trades
            if state.bot_slug in ["dm-bull", "dm-bear", "dominance-bull", "dominance-bear", "dominance_crypto"]:
                await self._trigger_reversal(db, state, user)
                state.status = "REVERSED"
                state.last_checked_at = datetime.now(timezone.utc)
                db.commit()

    async def _trigger_reversal(self, db, state: TradeState, user: User):
        # Double check reversal_used again (Safety Guard 1)
        if state.reversal_used:
            logger.warning(f"Reversal already used for {state.id}. Skipping.")
            return

        # Safety Guard 2: Symbol stacking check
        # Ensure no existing open position for this symbol before firing reversal
        # (MetaApi sync delay protection)
        from app.services.metaapi_service import has_open_position
        if await has_open_position(user.meta_account_id, state.symbol):
            logger.warning(f"Symbol stacking guard: {state.symbol} still has an open position. Delaying reversal.")
            return

        logger.info(f"🔄 Triggering REVERSAL for {state.user_id} on {state.symbol}")
        
        reverse_side = "sell" if state.side == "buy" else "buy"
        original_entry = _original_dom_entry(state)
        original_stop = _original_dom_stop(state)
        original_risk = _original_dom_risk(state)

        if original_risk <= 0:
            logger.warning(f"Reversal aborted for {state.id}: could not derive original DOM risk")
            return

        # Reversal is defined as a true 1:1 trade after the original DOM SL is hit:
        # - the reversal SL is anchored to the original DOM close/entry
        # - TP is projected exactly one risk unit away from the actual reversal fill
        #   (after we fetch the broker fill below)
        expected_reverse_entry = original_stop
        reversal_sl = original_entry
        provisional_tp = (
            expected_reverse_entry - original_risk
            if reverse_side == "sell"
            else expected_reverse_entry + original_risk
        )

        # Best-effort: reuse original trade volume when available.
        reverse_volume = 0.01
        try:
            from app.models.trade import Trade
            original_trade = db.query(Trade).filter(Trade.id == state.position_id).first()
            if original_trade and original_trade.lot_size:
                reverse_volume = float(original_trade.lot_size)
        except Exception:
            pass

        reverse_trade = {
            "symbol": state.symbol,
            "side": reverse_side,
            "entry": expected_reverse_entry,
            "sl": reversal_sl,
            "tp": provisional_tp,
            "be_trigger": 0,
            "volume": reverse_volume,
        }
        
        # Attempt to open
        response = await self.engine.open_trade(user, reverse_trade)
        if response and response.get("status") == "success":
            meta_result = response.get("result", {}) or {}
            string_code = meta_result.get("stringCode")
            pos_id = meta_result.get("positionId") or meta_result.get("orderId")
            if string_code not in ["TRADE_RETCODE_DONE", "TRADE_RETCODE_PLACED"] or not pos_id:
                logger.warning(f"Reversal rejected/unknown result: {string_code} {meta_result}")
                return

            # Fetch the opened position to capture real entry price (needed for BE logic)
            entry_price = None
            try:
                positions = await self.engine.get_positions(user.meta_account_id)
                match = next((p for p in positions if str(p.get("id")) == str(pos_id)), None)
                if not match:
                    match = next(
                        (p for p in positions
                         if p.get("symbol") == state.symbol and (p.get("type") or "").lower() == reverse_side.lower()),
                        None
                    )
                if match:
                    entry_price = float(match.get("openPrice") or match.get("price") or match.get("currentPrice") or 0)
            except Exception as e:
                logger.warning(f"Failed to fetch reversal position entry price: {e}")

            if not entry_price:
                entry_price = expected_reverse_entry

            actual_risk = abs(entry_price - reversal_sl)
            if actual_risk <= 0:
                logger.warning(f"Reversal aborted for {state.id}: invalid actual reversal risk")
                return

            exact_tp = (
                entry_price - actual_risk
                if reverse_side == "sell"
                else entry_price + actual_risk
            )
            be_trigger = (
                entry_price + (actual_risk * BE_TRIGGER_RATIO)
                if reverse_side == "buy"
                else entry_price - (actual_risk * BE_TRIGGER_RATIO)
            )

            updated_stops = await self.engine.update_position_stops(
                user,
                pos_id,
                reversal_sl,
                exact_tp,
            )
            if not updated_stops:
                logger.warning(
                    f"Failed to normalize reversal stops for {pos_id}. "
                    f"Keeping provisional SL/TP sl={reversal_sl} tp={provisional_tp}"
                )
                exact_tp = provisional_tp

            # Mark original as reversal_used
            state.reversal_used = True

            # Record reversal position/trade so UI + monitor can track it
            try:
                from app.services.position_tracker import PositionTracker
                PositionTracker().save_position({
                    "id": pos_id,
                    "user_id": user.id,
                    "symbol": state.symbol,
                    "side": reverse_side,
                    "entry": entry_price,
                    "sl": reversal_sl,
                    "tp": exact_tp,
                    "be_trigger": be_trigger,
                    "is_reversal": True,
                    "status": "OPEN",
                })

                from app.models.trade import Trade
                from datetime import timezone
                db.add(Trade(
                    id=pos_id,
                    user_id=user.id,
                    signal_id=None,
                    bot_id=None,
                    symbol=state.symbol,
                    side=reverse_side,
                    entry=entry_price,
                    lot_size=reverse_volume,
                    execution_time=datetime.now(timezone.utc),
                    status="OPEN",
                    result="OPEN",
                    metaapi_trade_id=pos_id,
                ))
            except Exception as e:
                logger.warning(f"Failed to persist reversal Trade/Position: {e}")

            # Mark original as reversal_used
            # Create NEW TradeState for the reversal
            ts = TradeState(
                user_id=user.id,
                symbol=state.symbol,
                position_id=pos_id,
                bot_slug=state.bot_slug,
                entry_price=entry_price,
                sl_price=reversal_sl,
                tp_price=exact_tp,
                be_trigger=be_trigger,
                dom_high=state.dom_high,
                dom_low=state.dom_low,
                dom_close=original_entry,
                dom_length=actual_risk,
                side=reverse_trade["side"],
                status="OPEN",
                reversal_used=True # Reversal can only happen once
            )
            db.add(ts)
            logger.info(f"Successfully fired REVERSAL trade for {user.id}")

    async def _reconcile_closed_mismatches(self, db):
        """
        Safety net: backfill trades/positions that are CLOSED in TradeState
        but still OPEN/CLOSING in reporting tables.
        """
        rows = db.query(TradeState, Trade).join(
            Trade, Trade.id == TradeState.position_id
        ).filter(
            TradeState.status.in_(["CLOSED", "REVERSED"]),
            Trade.status.in_(["OPEN", "CLOSING"])
        ).limit(100).all()

        if not rows:
            return

        user_rows = defaultdict(list)
        for state, trade in rows:
            user_rows[state.user_id].append((state, trade))

        for user_id, pairs in user_rows.items():
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                continue

            if not getattr(user, "can_trade", True):
                closed_count = force_close_orphaned_trades_for_user(
                    db, user.id, close_reason="ACCOUNT_INACTIVE"
                )
                if closed_count:
                    logger.warning(
                        f"Reconciliation force-closed {closed_count} orphaned trade(s) for inactive user {user.id}"
                    )
                continue

            if not user.meta_account_id:
                continue

            deals = await self.engine.get_deals(user.meta_account_id, days=30)
            close_by_pos = {}
            for d in deals:
                if d.get("entryType") != "DEAL_ENTRY_OUT":
                    continue
                close_by_pos[str(d.get("positionId"))] = d

            for state, trade in pairs:
                close_deal = close_by_pos.get(str(state.position_id))
                if not close_deal:
                    continue
                try:
                    exit_price = float(close_deal.get("price", 0))
                    pnl = (
                        float(close_deal.get("profit", 0) or 0)
                        + float(close_deal.get("swap", 0) or 0)
                        + float(close_deal.get("commission", 0) or 0)
                    )
                    deal_time = close_deal.get("time")
                    closed_at = datetime.now(timezone.utc)
                    if deal_time:
                        try:
                            closed_at = datetime.fromisoformat(deal_time.replace("Z", "+00:00"))
                        except Exception:
                            pass

                    pos = db.query(Position).filter(Position.id == state.position_id).first()
                    if pos:
                        pos.status = "CLOSED"
                        pos.exit_price = exit_price
                        pos.pnl = pnl
                        pos.closed_at = closed_at

                    trade.status = "CLOSED"
                    trade.result = "WIN" if pnl > 0 else ("LOSS" if pnl < 0 else "BE")
                    trade.exit = exit_price
                    trade.pnl = pnl
                    trade.close_time = closed_at
                    trade.last_synced_at = datetime.now(timezone.utc)
                    trade.retry_count = 0

                    if state.status == "CLOSING":
                        state.status = "CLOSED"
                    state.last_checked_at = datetime.now(timezone.utc)
                    logger.info(f"Reconciled stale close for position {state.position_id}")
                except Exception as e:
                    logger.error(f"Reconciliation failed for position {state.position_id}: {e}")
