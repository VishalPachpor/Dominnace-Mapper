from __future__ import annotations

from datetime import datetime, timezone

from app.models.position import Position
from app.models.trade import Trade
from app.models.trade_state import TradeState


ACTIVE_TRADE_STATUSES = ("OPEN", "CLOSING")
ACTIVE_STATE_STATUSES = ("OPEN", "BE_MOVED", "CLOSING")


def force_close_orphaned_trades_for_user(db, user_id: str, close_reason: str = "ACCOUNT_INACTIVE") -> int:
    """
    Mark all active trades for a user as CLOSING when broker sync is unavailable
    (for example account disconnected/expired). Caller controls transaction/commit.
    Final PnL and exit must still come from broker close data.
    """
    now = datetime.now(timezone.utc)
    trades = (
        db.query(Trade)
        .filter(Trade.user_id == user_id, Trade.status.in_(ACTIVE_TRADE_STATUSES))
        .all()
    )
    if not trades:
        return 0

    trade_ids = [t.id for t in trades]
    positions = (
        db.query(Position)
        .filter(Position.user_id == user_id, Position.id.in_(trade_ids))
        .all()
    )
    states = (
        db.query(TradeState)
        .filter(
            TradeState.user_id == user_id,
            TradeState.position_id.in_(trade_ids),
            TradeState.status.in_(ACTIVE_STATE_STATUSES),
        )
        .all()
    )

    pos_by_id = {p.id: p for p in positions}
    state_by_pos = {s.position_id: s for s in states}

    for trade in trades:
        trade.status = "CLOSING"
        trade.result = "OPEN"
        trade.reject_reason = trade.reject_reason or close_reason
        trade.last_synced_at = now
        trade.retry_count = int(trade.retry_count or 0) + 1

        pos = pos_by_id.get(trade.id)
        if pos:
            pos.status = "CLOSING"

        state = state_by_pos.get(trade.id)
        if state:
            state.status = "CLOSING"
            state.last_checked_at = now

    return len(trades)
