import logging
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, case
from collections import defaultdict
from app.database.db import get_db
from app.models.user import User
from app.models.bot import Bot
from app.models.trade import Trade
from app.models.strategy_stats import StrategyStats
from app.models.trade_state import TradeState
from app.utils.security import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()

DOMINANCE_STRATEGY_SLUGS = {
    "dm-bull",
    "dm-bear",
    "dominance-bull",
    "dominance-bear",
    "dominance_crypto",
    "dominance",
    "dom",
}


def _normalize_strategy_identity(bot_slug: str | None, bot_name: str | None = None) -> tuple[str, str]:
    slug = (bot_slug or "").strip().lower()
    name = (bot_name or "").strip()

    if (
        slug in DOMINANCE_STRATEGY_SLUGS
        or slug.startswith("dm-")
        or slug.startswith("dominance")
        or "dominance" in name.lower()
    ):
        return "dominance-mapper", "Dominance Mapper"

    normalized_slug = slug or "unknown-strategy"
    normalized_name = name or normalized_slug.replace("-", " ").replace("_", " ").title()
    return normalized_slug, normalized_name


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

    # 3b. Fallback: derive strategy data from the trades table when
    # StrategyStats has not been populated yet (no closed trades through
    # the trade monitor) but trades do exist.
    trades_map: dict[str, dict] = {}
    trade_rows = (
        db.query(
            Bot.slug,
            func.count(Trade.id).label("count"),
            func.coalesce(func.sum(Trade.pnl), 0.0).label("pnl"),
            func.sum(case((Trade.result == "WIN", 1), else_=0)).label("wins"),
            func.sum(case((Trade.result == "LOSS", 1), else_=0)).label("losses"),
        )
        .join(Bot, Trade.bot_id == Bot.id)
        .group_by(Bot.slug)
        .all()
    )
    for slug, count, pnl, wins, losses in trade_rows:
        trades_map[slug] = {
            "total_trades": int(count or 0),
            "total_pnl": float(pnl or 0.0),
            "wins": int(wins or 0),
            "losses": int(losses or 0),
        }

    logger.info(
        "[Strategies] sources: bots=%d, stats=%d, live_states=%d, trade_rows=%d",
        len(bots), len(stats_map), len(open_states), len(trades_map),
    )

    # 4. Merge into unified response.
    # Use bots as the preferred catalog, but fall back to live/stats/trades slugs so
    # strategies still appear even if the bots table is stale or missing rows.
    grouped_result = {}
    bot_by_slug = {bot.slug: bot for bot in bots}
    discovered_slugs = set(bot_by_slug.keys()) | set(stats_map.keys()) | set(live_map.keys()) | set(trades_map.keys())

    for raw_slug in discovered_slugs:
        bot = bot_by_slug.get(raw_slug)
        strategy_slug, strategy_name = _normalize_strategy_identity(raw_slug, bot.name if bot else None)
        bucket = grouped_result.setdefault(strategy_slug, {
            "bot_slug": strategy_slug,
            "bot_name": strategy_name,
            "is_active": False,
            "total_trades": 0,
            "wins": 0,
            "losses": 0,
            "total_pnl": 0.0,
            "open_trades": 0,
            "running_pnl": 0.0,
            "last_updated_dt": None,
        })

        s = stats_map.get(raw_slug)
        live = live_map.get(raw_slug, {"open_trades": 0, "running_pnl": 0.0})
        t = trades_map.get(raw_slug, {})

        source_is_active = bool(bot.is_active) if bot else True
        bucket["is_active"] = bucket["is_active"] or source_is_active

        # Prefer StrategyStats (authoritative), fall back to trades table aggregation
        if s:
            bucket["total_trades"] += int(s.total_trades or 0)
            bucket["wins"] += int(s.wins or 0)
            bucket["losses"] += int(s.losses or 0)
            bucket["total_pnl"] += float(s.total_pnl or 0.0)
        elif t:
            bucket["total_trades"] += t["total_trades"]
            bucket["wins"] += t["wins"]
            bucket["losses"] += t["losses"]
            bucket["total_pnl"] += t["total_pnl"]

        bucket["open_trades"] += int(live["open_trades"])
        bucket["running_pnl"] += float(live["running_pnl"])

        if s and s.last_updated and (
            bucket["last_updated_dt"] is None or s.last_updated > bucket["last_updated_dt"]
        ):
            bucket["last_updated_dt"] = s.last_updated

    result = []
    for strategy in grouped_result.values():
        result.append({
            "bot_slug": strategy["bot_slug"],
            "bot_name": strategy["bot_name"],
            "is_active": strategy["is_active"],
            "total_trades": strategy["total_trades"],
            "wins": strategy["wins"],
            "losses": strategy["losses"],
            "total_pnl": round(strategy["total_pnl"], 2),
            "open_trades": strategy["open_trades"],
            "running_pnl": round(strategy["running_pnl"], 2),
            "last_updated": strategy["last_updated_dt"].isoformat() if strategy["last_updated_dt"] else None,
        })

    result.sort(key=lambda item: (item["open_trades"] > 0, item["total_trades"], item["bot_name"]), reverse=True)
    return result
