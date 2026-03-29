from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta
from app.utils.security import get_current_user
from app.models.position import Position
from app.models.trade import Trade
from app.models.trade_state import TradeState
from app.database.db import get_db
from app.services.metaapi_service import get_open_positions, close_position, get_deal_history
import logging

logger = logging.getLogger(__name__)

router = APIRouter()
STALE_OPEN_GRACE_SECONDS = 120


def _mark_trade_closing(db: Session, trade: Trade, reason: str) -> None:
    now = datetime.now(timezone.utc)
    trade.status = "CLOSING"
    trade.result = "OPEN"
    trade.last_synced_at = now
    trade.retry_count = int(trade.retry_count or 0) + 1
    trade.reject_reason = trade.reject_reason or reason

    pos = db.query(Position).filter(Position.id == trade.id).first()
    if pos and pos.status in ("OPEN", "CLOSING"):
        pos.status = "CLOSING"

    state = db.query(TradeState).filter(TradeState.position_id == trade.id).first()
    if state and state.status in ("OPEN", "BE_MOVED", "CLOSING"):
        state.status = "CLOSING"
        state.last_checked_at = now


def _find_close_deal(position_id: str, deals: list[dict]) -> dict | None:
    position_id = str(position_id)
    for deal in deals:
        if deal.get("entryType") != "DEAL_ENTRY_OUT":
            continue
        if str(deal.get("positionId")) == position_id:
            return deal
    return None


def _apply_close_deal(db: Session, trade: Trade, close_deal: dict, reason: str) -> None:
    now = datetime.now(timezone.utc)
    commission = float(close_deal.get("commission", 0) or 0)
    swap = float(close_deal.get("swap", 0) or 0)
    pnl = float(close_deal.get("profit", 0) or 0) + commission + swap
    exit_price = float(close_deal.get("price", 0) or 0)
    deal_time = close_deal.get("time")
    closed_at = now
    if deal_time:
        try:
            closed_at = datetime.fromisoformat(deal_time.replace("Z", "+00:00"))
        except Exception:
            closed_at = now

    trade.status = "CLOSED"
    trade.result = "WIN" if pnl > 0 else ("LOSS" if pnl < 0 else "BE")
    trade.exit = exit_price
    trade.pnl = pnl
    trade.close_time = closed_at
    trade.last_synced_at = now
    trade.retry_count = 0
    trade.reject_reason = trade.reject_reason or reason

    pos = db.query(Position).filter(Position.id == trade.id).first()
    if pos:
        pos.status = "CLOSED"
        pos.exit_price = exit_price
        pos.pnl = pnl
        pos.closed_at = closed_at

    state = db.query(TradeState).filter(TradeState.position_id == trade.id).first()
    if state and state.status in ("OPEN", "BE_MOVED", "CLOSING"):
        state.status = "CLOSED"
        state.last_checked_at = now


def _finalize_stale_open_trade(
    db: Session,
    trade: Trade,
    reason: str,
    close_deal: dict | None = None,
    force_fallback_close: bool = False,
) -> None:
    if close_deal:
        _apply_close_deal(db, trade, close_deal, reason)
        return

    # Never fabricate a final breakeven close when the broker has not yet
    # provided the closing deal. Keep the trade in CLOSING until broker truth
    # is available and let reconciliation finish it later.
    _mark_trade_closing(db, trade, reason)


@router.get("")
async def get_positions(user=Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Returns OPEN/CLOSING positions from DB (single source of truth for UI).
    Broker is used for execution/sync, not for direct UI reads.
    """
    if not getattr(user, "can_trade", True):
        return []

    open_trades = db.query(Trade).filter(
        Trade.user_id == user.id,
        Trade.status.in_(["OPEN", "CLOSING"])
    ).order_by(Trade.execution_time.desc().nullslast(), Trade.created_at.desc()).all()

    # Reconcile stale OPEN rows against broker live positions so ghost rows are removed
    # before we return data to the UI.
    meta_account_id = getattr(user, "meta_account_id", None)
    broker_position_by_id: dict[str, dict] = {}
    if meta_account_id and open_trades:
        try:
            broker_positions = await get_open_positions(meta_account_id)
            broker_deals = await get_deal_history(meta_account_id)
            broker_position_by_id = {
                str(p.get("id")): p
                for p in broker_positions
                if p.get("id") is not None
            }
            live_ids = {str(p.get("id")) for p in broker_positions if p.get("id") is not None}
            cutoff = datetime.now(timezone.utc) - timedelta(seconds=STALE_OPEN_GRACE_SECONDS)
            closed_count = 0

            for t in open_trades:
                if str(t.id) in live_ids:
                    continue
                opened_at = t.execution_time or t.created_at
                if opened_at and opened_at.tzinfo is None:
                    opened_at = opened_at.replace(tzinfo=timezone.utc)
                if opened_at and opened_at > cutoff:
                    # Avoid racing very fresh orders with broker propagation delays.
                    continue
                close_deal = _find_close_deal(t.id, broker_deals)
                _finalize_stale_open_trade(
                    db,
                    t,
                    reason="BROKER_POSITION_NOT_FOUND",
                    close_deal=close_deal,
                )
                closed_count += 1

            if closed_count:
                db.commit()
                logger.warning(
                    f"Auto-closed {closed_count} stale OPEN/CLOSING trade(s) for user {user.id} in /positions reconciliation"
                )
                open_trades = db.query(Trade).filter(
                    Trade.user_id == user.id,
                    Trade.status.in_(["OPEN", "CLOSING"])
                ).order_by(Trade.execution_time.desc().nullslast(), Trade.created_at.desc()).all()
        except Exception as e:
            logger.warning(f"/positions broker reconciliation skipped for user {user.id}: {e}")

    result = []
    for t in open_trades:
        broker_pos = broker_position_by_id.get(str(t.id))
        current_price = float(broker_pos.get("currentPrice", 0)) if broker_pos else None
        pnl_val = float(broker_pos.get("profit", 0)) if broker_pos else (t.pnl if t.pnl is not None else 0.0)
        result.append({
            "id": t.id,
            "symbol": t.symbol,
            "side": t.side,
            "type": t.side,
            "volume": t.lot_size or 0.01,
            "entry_price": t.entry,
            "entry": t.entry,
            "current_price": current_price,
            "currentPrice": current_price,
            "pnl": pnl_val,
            "profit": pnl_val,
            "sl": None,
            "tp": None,
            "status": t.status,
            "result": t.result,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "execution_time": t.execution_time.isoformat() if t.execution_time else None,
            "last_synced_at": t.last_synced_at.isoformat() if getattr(t, "last_synced_at", None) else None,
        })
    return result


@router.post("/close-all")
async def close_all_positions(user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Close all open positions for the current user."""
    meta_account_id = getattr(user, "meta_account_id", None)
    if not meta_account_id:
        raise HTTPException(status_code=400, detail="No MetaApi account connected")

    try:
        broker_positions = await get_open_positions(meta_account_id)
        closed = 0
        errors = []

        for p in broker_positions:
            pid = p.get("id", "")
            try:
                await close_position(meta_account_id, pid)
                broker_deals = await get_deal_history(meta_account_id)
                trade = db.query(Trade).filter(Trade.user_id == user.id, Trade.id == str(pid)).first()
                if trade and trade.status in ("OPEN", "CLOSING"):
                    _finalize_stale_open_trade(
                        db,
                        trade,
                        reason="MANUAL_CLOSE_REQUESTED",
                        close_deal=_find_close_deal(pid, broker_deals),
                    )
                closed += 1
            except Exception as e:
                errors.append({"position_id": pid, "error": str(e)})
                logger.error(f"Failed to close position {pid}: {e}")

        if closed:
            db.commit()
        logger.info(f"User {user.id} closed {closed}/{len(broker_positions)} positions")
        return {"status": "done", "closed": closed, "total": len(broker_positions), "errors": errors}
    except Exception as e:
        logger.error(f"Failed to close all positions for user {user.id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to close positions: {str(e)}")


@router.post("/{position_id}/close")
async def close_single_position(position_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Close a specific position by its broker position ID."""
    meta_account_id = getattr(user, "meta_account_id", None)
    if not meta_account_id:
        raise HTTPException(status_code=400, detail="No MetaApi account connected")

    try:
        result = await close_position(meta_account_id, position_id)
        broker_deals = await get_deal_history(meta_account_id)
        trade = db.query(Trade).filter(Trade.user_id == user.id, Trade.id == str(position_id)).first()
        if trade and trade.status in ("OPEN", "CLOSING"):
            _finalize_stale_open_trade(
                db,
                trade,
                reason="MANUAL_CLOSE_REQUESTED",
                close_deal=_find_close_deal(position_id, broker_deals),
            )
            db.commit()
        logger.info(f"User {user.id} closed position {position_id}")
        return {"status": "closed", "result": result}
    except Exception as e:
        logger.error(f"Failed to close position {position_id} for user {user.id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to close position: {str(e)}")
