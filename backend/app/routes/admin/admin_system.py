from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import or_
import logging
from app.database.db import get_db
from app.models.user import User
from app.models.bot import Bot
from app.utils.security import get_current_user
from app.utils.redis_client import redis_client

router = APIRouter()
logger = logging.getLogger(__name__)

REDIS_KILL_SWITCH_KEY = "trading_enabled"

def require_admin(user: User = Depends(get_current_user)):
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user

@router.get("/")
def get_system_status(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """System health checks and counters."""
    # Redis Check
    redis_status = "connected"
    try:
        redis_client.ping()
    except:
        redis_status = "error"

    # Worker Stats (from Redis counters)
    signals_today = redis_client.get("signals_today") or 0
    trades_today = redis_client.get("trades_today") or 0
    
    # Platform High Level Stats
    total_users = db.query(User).count()
    active_mt_users = db.query(User).filter(
        or_(
            User.mt_status == "connected",
            User.ea_token.isnot(None)
        )
    ).count()

    trading_enabled = is_trading_enabled()

    return {
        "health": {
            "redis": redis_status,
            "metaapi": "OK", # Simplified for now
            "trading_engine": "RUNNING" if trading_enabled else "HALTED"
        },
        "counters": {
            "signals_today": int(signals_today),
            "trades_today": int(trades_today)
        },
        "observability": {
            "total_users": total_users,
            "active_mt_users": active_mt_users,
            "trading_enabled": trading_enabled
        }
    }

@router.post("/kill-switch")
def toggle_kill_switch(enable: bool, user: User = Depends(get_current_user)):
    """Stops or Resumes all trading platform-wide."""
    require_admin(user)
    redis_client.set(REDIS_KILL_SWITCH_KEY, "1" if enable else "0")
    status = "enabled" if enable else "disabled"
    logger.critical(f"Admin {user.id} {status} trading.")
    return {"status": status}

def is_trading_enabled() -> bool:
    val = redis_client.get(REDIS_KILL_SWITCH_KEY)
    if val is None: return True
    if isinstance(val, bytes): val = val.decode()
    return val == "1"
