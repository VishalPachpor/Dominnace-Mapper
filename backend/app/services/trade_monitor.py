import logging
import asyncio
from datetime import datetime
from app.database.db import SessionLocal
from app.models.trade_state import TradeState
from app.models.user import User
from app.services.execution_engine import ExecutionEngine
from app.services.trade_manager import TradeManager
from app.services.analytics import AnalyticsService

logger = logging.getLogger(__name__)

class TradeMonitorService:
    def __init__(self):
        self.engine = ExecutionEngine()
        self.manager = TradeManager()

    async def monitor_all_trades(self):
        db = SessionLocal()
        try:
            active_states = db.query(TradeState).filter(
                TradeState.status.in_(["OPEN", "BE_MOVED"])
            ).all()

            for state in active_states:
                try:
                    await self._process_state(db, state)
                except Exception as e:
                    logger.error(f"Error processing TradeState {state.id}: {e}")
            
            db.commit()
        finally:
            db.close()

    async def _process_state(self, db, state: TradeState):
        user = db.query(User).filter(User.id == state.user_id).first()
        if not user or not user.meta_account_id:
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
            if state.status == "OPEN":
                current_price = float(matching_pos["currentPrice"])
                triggered = False
                if state.side == "buy" and current_price >= state.be_trigger:
                    triggered = True
                elif state.side == "sell" and current_price <= state.be_trigger:
                    triggered = True
                
                if triggered:
                    logger.info(f"BE Triggered for {state.id} ({state.symbol}). Moving SL to {state.entry_price}")
                    success = await self.engine.update_position_sl(user, matching_pos["id"], state.entry_price)
                    if success:
                        state.status = "BE_MOVED"
                        state.sl_price = state.entry_price
                        db.commit()

        except Exception as e:
            logger.error(f"Failed to fetch/process MetaApi state for {state.user_id}: {e}")

    async def _handle_closed_position(self, db, state: TradeState, user: User):
        """
        Handles a closed position. If it closed at SL and is a DOM trade, trigger reversal.
        """
        logger.info(f"Trade {state.id} ({state.symbol}) detected as CLOSED.")

        # Check history to see if it was a Loss (SL hit)
        deals = await self.engine.get_deals(user.meta_account_id, limit=20)
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
            return

        # Now safe to mark CLOSED
        state.status = "CLOSED"
        db.commit()
        
        is_loss = False
        exit_price = None
        pnl = 0.0
        closed_at = None
        exit_price = float(last_deal.get("price", 0))
        pnl = float(last_deal.get("profit", 0))
        is_loss = pnl < 0
        # Capture the actual finish time from the deal
        deal_time = last_deal.get("time")
        if deal_time:
            try:
                closed_at = datetime.fromisoformat(deal_time.replace("Z", "+00:00"))
            except Exception:
                closed_at = datetime.utcnow()
        
        # Sync back to Position table for reporting
        if state.position_id:
            from app.models.position import Position
            pos = db.query(Position).filter(Position.id == state.position_id).first()
            if pos:
                pos.status = "CLOSED"
                pos.exit_price = exit_price
                pos.pnl = pnl
                pos.closed_at = closed_at or datetime.utcnow()
                logger.info(f"Synced exit data for Position {pos.id} (Price: {exit_price}, PnL: {pnl})")
                
                from app.models.trade import Trade
                trade_record = db.query(Trade).filter(Trade.id == state.position_id).first()
                if trade_record:
                    trade_record.status = "CLOSED"
                    trade_record.close_time = pos.closed_at
                    trade_record.exit = exit_price
                    trade_record.pnl = pnl
                    logger.info(f"Synced exit data for Trade(CLOSED) {trade_record.id}")

                # Update Analytics
                AnalyticsService.update_trade_metrics(db, state.bot_slug, pnl)
        
        if is_loss and not state.reversal_used:
            # TRIGGER REVERSAL — only for DOM trades
            if state.bot_slug in ["dm-bull", "dm-bear", "dominance-bull", "dominance-bear", "dominance_crypto"]:
                await self._trigger_reversal(db, state, user)
                state.status = "REVERSED"
            # else: already CLOSED from the early commit above

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
        
        # Calculate Reversal Parameters
        # For BUY Reversal (SELL): SL = dom_high, TP = dom_low - dom_length
        # We need dom_high/low/length. We can derive them from original state.
        # Original BUY SL was dom_low. Original TP was dom_high + dom_length.
        # This implies:
        # dom_low = state.sl_price
        # dom_length = (state.tp_price - state.entry_price) # Rough, if it was 1:1
        # Correct way: pass it in? No, let's derive or use local logic.
        
        # In trade_manager.py we saved them to state. 
        # Let's assume we can get dom_length from (state.be_trigger - state.entry_price) / 0.35
        dom_length = (state.be_trigger - state.entry_price) / 0.35 if state.side == "buy" else (state.entry_price - state.be_trigger) / 0.35
        dom_length = abs(dom_length)
        
        if reverse_side == "sell":
            # State was BUY. dom_low = state.sl_price. dom_high = dom_low + dom_length.
            dom_low = state.sl_price
            dom_high = dom_low + dom_length
            sl = dom_high
            tp = dom_low - dom_length
        else:
            # State was SELL. dom_high = state.sl_price. dom_low = dom_high - dom_length.
            dom_high = state.sl_price
            dom_low = dom_high - dom_length
            sl = dom_low
            tp = dom_high + dom_length

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
            "entry": 0, # Market execution (we will fill actual entry from MetaApi positions)
            "sl": sl,
            "tp": tp,
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
                entry_price = state.entry_price

            be_trigger = entry_price + (dom_length * 0.35) if reverse_side == "buy" else entry_price - (dom_length * 0.35)

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
                    "sl": sl,
                    "tp": tp,
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
                    status="EXECUTED",
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
                sl_price=reverse_trade["sl"],
                tp_price=reverse_trade["tp"],
                be_trigger=be_trigger,
                side=reverse_trade["side"],
                status="OPEN",
                reversal_used=True # Reversal can only happen once
            )
            db.add(ts)
            logger.info(f"Successfully fired REVERSAL trade for {user.id}")
