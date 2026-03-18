from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from collections import defaultdict
from app.database.db import get_db
from app.models.user import User
from app.models.bot import Bot
from app.models.strategy_stats import StrategyStats
from app.models.trade_state import TradeState
from app.utils.security import get_current_user

router = APIRouter()


def require_admin(user: User = Depends(get_current_user)):
    if not user.is_admin:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


@router.get("/")
def get_strategy_stats(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """
    Get aggregated performance stats per strategy.
    Merges:
      - Active bots (always shown even with 0 trades)
      - Historical StrategyStats (wins, losses, closed pnl)
      - Live open trades from TradeState (open_trades, running_pnl)
    """
    # 1. All active bots
    bots = db.query(Bot).filter(Bot.is_active == True).all()

    # 2. Historical stats — keyed by bot_slug
    stats_map = {s.bot_slug: s for s in db.query(StrategyStats).all()}

    # 3. Live positions — keyed by the bot_slug that opened them
    live_map = defaultdict(lambda: {"open_trades": 0, "running_pnl": 0.0})
    open_states = db.query(TradeState).filter(
        TradeState.status.in_(["OPEN", "BE_MOVED"])
    ).all()
    
    # 3a. Fix N+1 Query: Fetch all related positions in a single query
    pos_ids = [s.position_id for s in open_states if s.position_id]
    positions_map = {}
    if pos_ids:
        from app.models.position import Position
        positions = db.query(Position).filter(Position.id.in_(pos_ids)).all()
        positions_map = {p.id: p for p in positions}

    for state in open_states:
        live_map[state.bot_slug]["open_trades"] += 1
        pos = positions_map.get(state.position_id)
        if pos:
            live_map[state.bot_slug]["running_pnl"] += pos.unrealized_pnl or 0.0

    # 4. Merge into unified response
    result = []
    for bot in bots:
        s = stats_map.get(bot.slug)
        live = live_map.get(bot.slug, {"open_trades": 0, "running_pnl": 0.0})

        result.append({
            "bot_slug": bot.slug,
            "bot_name": bot.name,
            "is_active": bot.is_active,
            "total_trades": s.total_trades if s else 0,
            "wins": s.wins if s else 0,
            "losses": s.losses if s else 0,
            "total_pnl": s.total_pnl if s else 0.0,
            "open_trades": live["open_trades"],
            "running_pnl": round(live["running_pnl"], 2),
            "last_updated": s.last_updated.isoformat() if s and s.last_updated else None,
        })

    return result
