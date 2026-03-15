from fastapi import APIRouter, HTTPException, Depends
from app.utils.security import get_current_user
from app.models.user import User
from app.utils.redis_client import redis_client
import logging
from sqlalchemy.orm import Session
from app.database.db import get_db

router = APIRouter()
logger = logging.getLogger(__name__)

# ─── Risk Limit Defaults ───
PLAN_LIMITS = {
    "starter": {"max_trades_per_hour": 5,  "max_bots": 1, "max_symbols": 1},
    "pro":     {"max_trades_per_hour": 20, "max_bots": 3, "max_symbols": 5},
    "elite":   {"max_trades_per_hour": 100, "max_bots": 99, "max_symbols": 99},
}

REDIS_KILL_SWITCH_KEY = "trading_enabled"


def _require_admin(user: User):
    """Raises 403 if the user is not an admin."""
    if not getattr(user, "is_admin", False):
        raise HTTPException(status_code=403, detail="Admin access required.")


@router.post("/stop-trading")
def kill_switch(user: User = Depends(get_current_user)):
    """Global kill switch — stops all trade execution immediately."""
    _require_admin(user)
    redis_client.set(REDIS_KILL_SWITCH_KEY, "0")
    logger.critical("🚨 KILL SWITCH ACTIVATED — All trading halted by %s.", user.id)
    return {"status": "trading_disabled", "message": "All trade execution has been halted."}


@router.post("/start-trading")
def resume_trading(user: User = Depends(get_current_user)):
    """Resumes trade execution after a kill switch."""
    _require_admin(user)
    redis_client.set(REDIS_KILL_SWITCH_KEY, "1")
    logger.info("✅ Trading resumed by %s.", user.id)
    return {"status": "trading_enabled", "message": "Trade execution has been resumed."}


@router.get("/status")
def trading_status():
    """Check whether the trading engine is enabled or disabled."""
    return {"trading_enabled": is_trading_enabled()}


@router.get("/stats")
def get_admin_stats(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Provides high-level multi-tenant statistics for the admin dashboard."""
    _require_admin(user)
    from sqlalchemy import or_
    from app.models.bot import Bot

    active_bots = db.query(Bot).filter(Bot.is_active == True).count()

    connected_users = db.query(User).filter(
        or_(
            User.mt_status == "connected",
            User.ea_token.isnot(None)
        )
    ).count()

    total_users = db.query(User).count()
    disconnected_users = total_users - connected_users

    return {
        "active_bots": active_bots,
        "connected_users": connected_users,
        "disconnected_users": disconnected_users,
        "total_users": total_users
    }


@router.get("/limits/{plan}")
def get_plan_limits(plan: str, user: User = Depends(get_current_user)):
    """Get the risk control limits for a given subscription plan."""
    _require_admin(user)
    limits = PLAN_LIMITS.get(plan)
    if not limits:
        raise HTTPException(status_code=404, detail=f"Unknown plan: {plan}")
    return limits


def is_trading_enabled() -> bool:
    """
    Helper used by workers/services to check global state before executing.
    Reads from Redis so it survives server restarts.
    Defaults to True (enabled) if the key doesn't exist yet.
    """
    val = redis_client.get(REDIS_KILL_SWITCH_KEY)
    if val is None:
        return True
    if isinstance(val, bytes):
        val = val.decode()
    return val == "1"
