from fastapi import APIRouter, HTTPException, Depends
from app.utils.security import get_current_user
from app.models.user import User
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

# ─── Global Trading State ───
trading_enabled = True

# ─── Risk Limit Defaults ───
PLAN_LIMITS = {
    "starter": {"max_trades_per_hour": 5,  "max_bots": 1, "max_symbols": 1},
    "pro":     {"max_trades_per_hour": 20, "max_bots": 3, "max_symbols": 5},
    "elite":   {"max_trades_per_hour": 100, "max_bots": 99, "max_symbols": 99},
}


@router.post("/stop-trading")
def kill_switch(user: User = Depends(get_current_user)):
    """Global kill switch — stops all trade execution immediately."""
    global trading_enabled
    trading_enabled = False
    logger.critical("🚨 KILL SWITCH ACTIVATED — All trading halted.")
    return {"status": "trading_disabled", "message": "All trade execution has been halted."}


@router.post("/start-trading")
def resume_trading(user: User = Depends(get_current_user)):
    """Resumes trade execution after a kill switch."""
    global trading_enabled
    trading_enabled = True
    logger.info("✅ Trading resumed.")
    return {"status": "trading_enabled", "message": "Trade execution has been resumed."}


@router.get("/status")
def trading_status():
    """Check whether the trading engine is enabled or disabled."""
    return {"trading_enabled": trading_enabled}


@router.get("/limits/{plan}")
def get_plan_limits(plan: str):
    """Get the risk control limits for a given subscription plan."""
    limits = PLAN_LIMITS.get(plan)
    if not limits:
        raise HTTPException(status_code=404, detail=f"Unknown plan: {plan}")
    return limits


def is_trading_enabled():
    """Helper function used by workers/services to check global state before executing."""
    return trading_enabled
