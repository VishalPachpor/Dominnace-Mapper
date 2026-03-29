import asyncio
from datetime import datetime, timedelta, timezone
from time import perf_counter

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import or_
from pydantic import BaseModel
import logging
from app.database.db import get_db
from app.models.user import User
from app.models.bot import Bot
from app.utils.security import get_current_user
from app.utils.redis_client import redis_client
from app.services.metaapi_service import (
    inspect_metaapi_account_groups,
    cleanup_duplicate_metaapi_accounts,
    _list_metaapi_accounts,
)
from app.routes.users import _refresh_user_mt_state

router = APIRouter()
logger = logging.getLogger(__name__)

REDIS_KILL_SWITCH_KEY = "trading_enabled"
METAAPI_ACCOUNTS_CACHE_TTL_SECONDS = 30
_metaapi_accounts_cache_lock = asyncio.Lock()
_metaapi_accounts_cache: dict = {
    "expires_at": None,
    "signature": None,
    "payload": None,
}
_metaapi_re_evaluate_lock = asyncio.Lock()
_metaapi_re_evaluate_last_run_at: datetime | None = None

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
    except Exception as e:
        logger.warning(f"Redis health check failed: {e}")
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

class KillSwitchRequest(BaseModel):
    enabled: bool

@router.post("/kill-switch")
def toggle_kill_switch(body: KillSwitchRequest, admin: User = Depends(require_admin)):
    """Stops or Resumes all trading platform-wide."""
    redis_client.set(REDIS_KILL_SWITCH_KEY, "1" if body.enabled else "0")
    status = "enabled" if body.enabled else "disabled"
    logger.critical(f"Admin {admin.id} {status} trading.")
    return {"status": status, "message": f"Trading {status}"}

@router.post("/reset-counters")
def reset_counters(admin: User = Depends(require_admin)):
    """Resets daily signal and trade counters."""
    redis_client.set("signals_today", 0)
    redis_client.set("trades_today", 0)
    logger.info(f"Admin {admin.id} reset daily counters.")
    return {"status": "counters_reset"}

def is_trading_enabled() -> bool:
    val = redis_client.get(REDIS_KILL_SWITCH_KEY)
    if val is None: return True
    if isinstance(val, bytes): val = val.decode()
    return val == "1"


@router.get("/metaapi/accounts")
async def get_metaapi_accounts_view(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    linked_rows = (
        db.query(User.id, User.meta_account_id)
        .filter(User.meta_account_id.isnot(None))
        .all()
    )
    linked_user_by_account = {
        str(meta_account_id): str(user_id)
        for user_id, meta_account_id in linked_rows
        if meta_account_id
    }
    signature = tuple(sorted(linked_user_by_account.items()))
    now = datetime.now(timezone.utc)

    cached_payload = _metaapi_accounts_cache.get("payload")
    cached_signature = _metaapi_accounts_cache.get("signature")
    cached_expires_at = _metaapi_accounts_cache.get("expires_at")

    if (
        cached_payload is not None
        and cached_signature == signature
        and isinstance(cached_expires_at, datetime)
        and cached_expires_at > now
    ):
        return {**cached_payload, "is_snapshot": True}

    async with _metaapi_accounts_cache_lock:
        now = datetime.now(timezone.utc)
        cached_payload = _metaapi_accounts_cache.get("payload")
        cached_signature = _metaapi_accounts_cache.get("signature")
        cached_expires_at = _metaapi_accounts_cache.get("expires_at")
        if (
            cached_payload is not None
            and cached_signature == signature
            and isinstance(cached_expires_at, datetime)
            and cached_expires_at > now
        ):
            return {**cached_payload, "is_snapshot": True}

        groups = await inspect_metaapi_account_groups(linked_user_by_account)
        payload = {
            "groups": groups,
            "last_evaluated_at": now.isoformat(),
            "is_snapshot": False,
        }
        _metaapi_accounts_cache["payload"] = payload
        _metaapi_accounts_cache["signature"] = signature
        _metaapi_accounts_cache["expires_at"] = now + timedelta(seconds=METAAPI_ACCOUNTS_CACHE_TTL_SECONDS)
        return payload


def _invalidate_metaapi_accounts_cache() -> None:
    _metaapi_accounts_cache["payload"] = None
    _metaapi_accounts_cache["signature"] = None
    _metaapi_accounts_cache["expires_at"] = None


def _invalidate_metaapi_runtime_cache(account_ids: list[str]) -> None:
    try:
        keys: list[str] = []
        for account_id in account_ids:
            keys.extend([
                f"mt_status:{account_id}",
                f"positions:{account_id}",
                f"acct_info:{account_id}",
                f"deal_history:{account_id}",
            ])
        if keys:
            redis_client.delete(*keys)
    except Exception as e:
        logger.warning("Failed to invalidate MetaApi runtime cache: %s", e)


@router.post("/metaapi/re-evaluate")
async def re_evaluate_metaapi_accounts(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    global _metaapi_re_evaluate_last_run_at

    if _metaapi_re_evaluate_lock.locked():
        return {"status": "busy", "forced": False}

    now = datetime.now(timezone.utc)
    if (
        _metaapi_re_evaluate_last_run_at is not None
        and (now - _metaapi_re_evaluate_last_run_at) < timedelta(seconds=10)
    ):
        return {
            "status": "rate_limited",
            "forced": False,
            "retry_after_seconds": 10 - int((now - _metaapi_re_evaluate_last_run_at).total_seconds()),
        }

    started = perf_counter()
    async with _metaapi_re_evaluate_lock:
        _metaapi_re_evaluate_last_run_at = datetime.now(timezone.utc)
        _invalidate_metaapi_accounts_cache()

        accounts = await _list_metaapi_accounts()
        account_ids = [
            str(acct.get("_id") or acct.get("id"))
            for acct in accounts
            if acct.get("_id") or acct.get("id")
        ]
        _invalidate_metaapi_runtime_cache(account_ids)

        users = (
            db.query(User)
            .filter(User.meta_account_id.isnot(None))
            .all()
        )
        rebinds_triggered = 0
        for user in users:
            old_account_id = getattr(user, "meta_account_id", None)
            old_can_trade = bool(getattr(user, "can_trade", False))
            await _refresh_user_mt_state(user, db)
            new_account_id = getattr(user, "meta_account_id", None)
            new_can_trade = bool(getattr(user, "can_trade", False))
            if old_account_id != new_account_id or old_can_trade != new_can_trade:
                rebinds_triggered += 1

        cleanup_result = await cleanup_duplicate_metaapi_accounts()
        linked_rows = (
            db.query(User.id, User.meta_account_id)
            .filter(User.meta_account_id.isnot(None))
            .all()
        )
        linked_user_by_account = {
            str(meta_account_id): str(user_id)
            for user_id, meta_account_id in linked_rows
            if meta_account_id
        }
        groups = await inspect_metaapi_account_groups(linked_user_by_account)
        evaluated_at = datetime.now(timezone.utc)
        payload = {
            "groups": groups,
            "last_evaluated_at": evaluated_at.isoformat(),
            "is_snapshot": False,
        }
        _metaapi_accounts_cache["payload"] = payload
        _metaapi_accounts_cache["signature"] = tuple(sorted(linked_user_by_account.items()))
        _metaapi_accounts_cache["expires_at"] = evaluated_at + timedelta(seconds=METAAPI_ACCOUNTS_CACHE_TTL_SECONDS)

        duration_ms = int((perf_counter() - started) * 1000)
        return {
            "status": "ok",
            "forced": True,
            "evaluated_at": evaluated_at.isoformat(),
            "groups_count": len(groups),
            "rebinds_triggered": rebinds_triggered,
            "cleanup_actions": int(cleanup_result.get("undeployed_count", 0)),
            "duration_ms": duration_ms,
        }
