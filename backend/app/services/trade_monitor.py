import logging
import asyncio
from datetime import datetime
from app.database.db import SessionLocal
from app.models.trade_state import TradeState
from app.models.user import User
from app.services.execution_engine import ExecutionEngine
from app.services.trade_manager import TradeManager

logger = logging.getLogger(__name__)

class TradeMonitorService:
    def __init__(self):
        self.engine = ExecutionEngine()
        self.manager = TradeManager()

    async def monitor_all_trades(self):
        db = SessionLocal()
        try:
            active_states = db.query(TradeState).filter(
                TradeState.status.in_(["OPEN", "BREAKEVEN"])
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
            # Find matching position by symbol and side (rough check, could be improved with ticket ID if we stored it)
            # In Phase 1 we started saving positionId in TradeState if possible, but for now we match by symbol/side
            # to be safe across different broker behaviors.
            matching_pos = next((p for p in positions if p["symbol"] == state.symbol and p["type"].lower() == state.side.lower()), None)
            
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
                        state.status = "BREAKEVEN"
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
        # For simplicity in this version, if it's closed and reversal_used is False, 
        # we check if price was near SL or if we can get the last deal.
        # But per requirements: "If trade closes in LOSS (SL hit), immediately fire reversal".
        
        # Logic to determine if SL hit:
        # We can look up the last deal for this symbol in the last hour.
        deals = await self.engine.get_deals(user.meta_account_id, limit=5)
        last_deal = next((d for d in deals if d["symbol"] == state.symbol and d["entryType"] == "DEAL_ENTRY_OUT"), None)
        
        is_loss = False
        if last_deal:
            pnl = float(last_deal.get("profit", 0))
            is_loss = pnl < 0
            # Also double check it's not a tiny loss (fees) vs a real SL hit
            # if abs(float(last_deal['price']) - state.sl_price) < (state.entry_price * 0.001): is_loss = True
        
        if is_loss and not state.reversal_used:
            # TRIGGER REVERSAL
            # Only for DOM trades (determined by bot_slug)
            if state.bot_slug in ["dm-bull", "dm-bear", "dominance-bull", "dominance-bear"]:
                await self._trigger_reversal(db, state, user)
                state.status = "REVERSED"
            else:
                state.status = "CLOSED"
        else:
            state.status = "CLOSED"
        
        db.commit()

    async def _trigger_reversal(self, db, state: TradeState, user: User):
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

        reverse_trade = {
            "symbol": state.symbol,
            "side": reverse_side,
            "entry": 0, # Market execution
            "sl": sl,
            "tp": tp,
            "be_trigger": sl + (dom_length * 0.35) if reverse_side == "buy" else sl - (dom_length * 0.35),
            "volume": 0.01, # Should be the same as original? We could track it.
        }
        
        # Attempt to open
        response = await self.engine.open_trade(user, reverse_trade)
        if response:
            # Mark original as reversal_used
            state.reversal_used = True
            
            # Create NEW TradeState for the reversal
            ts = TradeState(
                user_id=user.id,
                symbol=state.symbol,
                bot_slug=state.bot_slug,
                entry_price=reverse_trade["entry"], # Will be updated by execution engine/monitor later
                sl_price=reverse_trade["sl"],
                tp_price=reverse_trade["tp"],
                be_trigger=reverse_trade["be_trigger"],
                side=reverse_trade["side"],
                status="OPEN",
                reversal_used=True # Reversal can only happen once
            )
            db.add(ts)
            logger.info(f"Successfully fired REVERSAL trade for {user.id}")
