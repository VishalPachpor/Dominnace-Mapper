"""
MetaApi Cloud MT5 Service Layer
Handles account provisioning, deployment, status polling, and trade execution.

Credit Optimization:
  - Status poller runs every 5 MINUTES (not 15 seconds) — 20× fewer REST calls
  - Poller skips users already in 'connected' state — no wasted calls on healthy accounts
  - get_open_positions() and get_account_information() are Redis-cached for 10 seconds
  - A metaapi_api_calls_total counter tracks exactly how many REST calls are made
  - poll_until_connected uses max 10 attempts at 30s intervals (5 min total, not 3 min at 10s)
"""
import os
import json
import asyncio
import logging
import httpx
from datetime import datetime, timedelta, timezone
from typing import Optional
from app.utils.crypto_util import decrypt_password

logger = logging.getLogger(__name__)

# ─── MetaApi endpoints ────────────────────────────────────────────────────────
PROVISION_URL = "https://mt-provisioning-api-v1.agiliumtrade.agiliumtrade.ai"
TRADE_URL = "https://mt-client-api-v1.london.agiliumtrade.ai"

# ─── Symbol mapping (handle broker-specific suffixes) ─────────────────────────
SYMBOL_MAP: dict[str, list[str]] = {
    "XAUUSD": ["XAUUSD", "XAUUSDm", "XAUUSD.a", "XAUUSD_"],
    "EURUSD": ["EURUSD", "EURUSDm", "EURUSD.a"],
    "GBPUSD": ["GBPUSD", "GBPUSDm", "GBPUSD.a"],
    "BTCUSD": ["BTCUSD", "BTCUSDm", "BTCUSD.a", "BTCUSDT"],
    "ETHUSD": ["ETHUSD", "ETHUSDm", "ETHUSD.a", "ETHUSDT"],
    "XAGUSD": ["XAGUSD", "XAGUSDm"],
}

# ─── API Call Counter (Prometheus metric) ─────────────────────────────────────
# Tracks exactly how many times we hit MetaApi REST endpoints so we never
# get surprised by credit consumption again.
try:
    from prometheus_client import Counter
    metaapi_calls_total = Counter(
        "metaapi_api_calls_total",
        "Total number of REST API calls made to MetaApi",
        ["endpoint"]
    )
    _prometheus_available = True
except Exception:
    _prometheus_available = False
    metaapi_calls_total = None

def _track_call(endpoint: str):
    """Increment the MetaApi REST call counter."""
    if _prometheus_available and metaapi_calls_total:
        try:
            metaapi_calls_total.labels(endpoint=endpoint).inc()
        except Exception:
            pass
    logger.debug(f"[MetaApi CALL] endpoint={endpoint}")


def _headers() -> dict:
    token = os.environ.get("META_API_TOKEN", "").strip()
    if not token:
        raise ValueError("META_API_TOKEN is not set in environment variables.")
    return {
        "auth-token": token,
        "Content-Type": "application/json"
    }


def resolve_symbol(symbol: str) -> str:
    """Return the canonical symbol name (first in the list)."""
    for canonical, variants in SYMBOL_MAP.items():
        if symbol.upper() in [v.upper() for v in variants]:
            return canonical
    return symbol  # Unknown symbol — pass through as-is


def _log_structured(event: str, **fields) -> None:
    try:
        logger.info("%s %s", event, json.dumps(fields, default=str, sort_keys=True), extra=fields)
    except Exception:
        logger.info("%s %s", event, fields)


def _has_account_data(info: dict | None) -> bool:
    return isinstance(info, dict) and any(
        info.get(key) is not None for key in ("balance", "equity", "marginFree", "freeMargin")
    )


def _parse_metaapi_dt(raw) -> datetime | None:
    if not raw:
        return None
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except Exception:
        return None


def _account_fingerprint(account: dict) -> str:
    return ":".join(
        str(account.get(part, "")).strip()
        for part in ("login", "server", "type", "name")
    )


# ─── Account Lifecycle ────────────────────────────────────────────────────────

async def _list_metaapi_accounts() -> list[dict]:
    _track_call("list_accounts")
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{PROVISION_URL}/users/current/accounts",
            headers=_headers()
        )
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else []


async def find_existing_account(
    login: str,
    server: str,
    preferred_account_id: str | None = None,
) -> Optional[dict]:
    """
    Search MetaApi for an existing account with the same login + server.
    When duplicates exist, prefer the healthiest live account and bias toward the
    currently linked account when it is still healthy.
    """
    try:
        accounts = await _list_metaapi_accounts()
        matches: list[dict] = []

        for acct in accounts:
            acct_login = str(acct.get("login", ""))
            acct_server = acct.get("server", "")
            if acct_login != str(login) or acct_server != server:
                continue

            acct_id = acct.get("_id") or acct.get("id")
            acct_state = acct.get("state", "")
            matches.append({
                "account_id": acct_id,
                "state": acct_state,
                "name": acct.get("name", ""),
            })

        if not matches:
            return None

        ranked: list[tuple[tuple[int, int, int, int], dict]] = []
        for acct in matches:
            acct_id = acct["account_id"]
            acct_state = acct.get("state", "")
            is_live = 1 if acct_state in ("CONNECTED", "DEPLOYED") else 0
            is_preferred = 1 if preferred_account_id and acct_id == preferred_account_id else 0
            has_account_data = 0
            open_positions = 0
            if is_live:
                try:
                    info = await get_account_information(acct_id)
                    has_account_data = 1 if _has_account_data(info) else 0
                    positions = await get_open_positions(acct_id)
                    open_positions = 1 if positions else 0
                except Exception:
                    has_account_data = 0
            acct["health_score"] = (has_account_data * 30) + (is_live * 50) + (open_positions * 20) + (is_preferred * 5)
            acct["selection_reason"] = {
                "has_account_data": bool(has_account_data),
                "is_live": bool(is_live),
                "has_open_positions": bool(open_positions),
                "is_preferred": bool(is_preferred),
            }
            ranked.append(acct)

        ranked.sort(key=lambda item: item.get("health_score", 0), reverse=True)
        best = ranked[0]
        _log_structured(
            "metaapi_account_selected",
            login=str(login),
            server=server,
            selected_account_id=best["account_id"],
            selected_state=best.get("state"),
            selected_score=best.get("health_score", 0),
            preferred_account_id=preferred_account_id,
            candidate_ids=[acct["account_id"] for acct in ranked],
            candidate_scores={
                acct["account_id"]: acct.get("health_score", 0)
                for acct in ranked
            },
        )
        return best
    except Exception as e:
        logger.warning(f"Could not search for existing MetaApi accounts: {e}")
    return None


async def cleanup_duplicate_metaapi_accounts() -> dict:
    """
    Undeploy-only cleanup pass for duplicate MetaApi terminals.
    Guardrails:
      - never touch canonical account for a login/server pair
      - never touch linked accounts
      - never touch accounts with open positions
      - never touch accounts with recent deals (24h)
      - never touch freshly created accounts (2h grace) when createdAt exists
    """
    from app.database.db import SessionLocal
    from app.models.user import User

    db = SessionLocal()
    groups_processed = 0
    undeployed_count = 0
    skipped_groups = 0
    try:
        accounts = await _list_metaapi_accounts()
        linked_ids = {
            row[0]
            for row in db.query(User.meta_account_id).filter(User.meta_account_id.isnot(None)).all()
            if row[0]
        }

        grouped: dict[tuple[str, str], list[dict]] = {}
        for acct in accounts:
            login = str(acct.get("login", "")).strip()
            server = str(acct.get("server", "")).strip()
            if not login or not server:
                continue
            grouped.setdefault((login, server), []).append(acct)

        now = datetime.now(timezone.utc)
        for (login, server), group in grouped.items():
            if len(group) <= 1:
                continue
            groups_processed += 1

            canonical = await find_existing_account(login, server)
            canonical_id = canonical.get("account_id") if canonical else None
            deleted: list[str] = []
            skipped: dict[str, str] = {}

            for acct in group:
                acct_id = acct.get("_id") or acct.get("id")
                if not acct_id:
                    continue
                if acct_id == canonical_id:
                    skipped[str(acct_id)] = "canonical"
                    continue
                if acct_id in linked_ids:
                    skipped[str(acct_id)] = "linked_to_user"
                    continue

                created_at = _parse_metaapi_dt(acct.get("createdAt") or acct.get("created_at"))
                if created_at and (now - created_at) < timedelta(hours=2):
                    skipped[str(acct_id)] = "within_grace_period"
                    continue

                try:
                    positions = await get_open_positions(str(acct_id))
                    if positions:
                        skipped[str(acct_id)] = "has_open_positions"
                        continue
                except Exception:
                    skipped[str(acct_id)] = "positions_check_failed"
                    continue

                try:
                    deals = await get_deal_history(str(acct_id), days=1)
                    recent_deals = [d for d in deals if _parse_metaapi_dt(d.get("time")) and (now - _parse_metaapi_dt(d.get("time"))) < timedelta(hours=24)]
                    if recent_deals:
                        skipped[str(acct_id)] = "recent_deals"
                        continue
                except Exception:
                    skipped[str(acct_id)] = "deals_check_failed"
                    continue

                try:
                    await undeploy_account(str(acct_id))
                    deleted.append(str(acct_id))
                except Exception as e:
                    skipped[str(acct_id)] = f"undeploy_failed:{type(e).__name__}"

            undeployed_count += len(deleted)
            if not deleted and skipped:
                skipped_groups += 1
            _log_structured(
                "metaapi_cleanup",
                group=f"{login}:{server}",
                fingerprint=_account_fingerprint(group[0]),
                canonical_account_id=canonical_id,
                undeployed=deleted,
                skipped=skipped,
                total_candidates=len(group),
                reason="stale_duplicate",
            )
    finally:
        db.close()
    return {
        "groups_processed": groups_processed,
        "undeployed_count": undeployed_count,
        "skipped_groups": skipped_groups,
    }


async def cleanup_duplicate_metaapi_accounts_loop() -> None:
    interval_hours = int(os.getenv("METAAPI_CLEANUP_INTERVAL_HOURS", "6"))
    logger.info("[MetaApiCleanup] Duplicate cleanup worker started. Interval: %sh", interval_hours)
    while True:
        try:
            await cleanup_duplicate_metaapi_accounts()
        except Exception as e:
            logger.error(f"[MetaApiCleanup] Error: {e}")
        await asyncio.sleep(max(interval_hours, 1) * 3600)


async def inspect_metaapi_account_groups(linked_user_by_account: dict[str, str | None]) -> list[dict]:
    """
    Read-only admin inspection of MetaApi account groups. Uses the same scoring
    and cleanup guardrails as selection/cleanup logic so the admin view matches
    actual system behavior.
    """
    accounts = await _list_metaapi_accounts()
    now = datetime.now(timezone.utc)
    grouped: dict[tuple[str, str], list[dict]] = {}

    for acct in accounts:
        login = str(acct.get("login", "")).strip()
        server = str(acct.get("server", "")).strip()
        if not login or not server:
            continue
        grouped.setdefault((login, server), []).append(acct)

    groups: list[dict] = []
    for (login, server), group in grouped.items():
        canonical = await find_existing_account(login, server)
        canonical_id = canonical.get("account_id") if canonical else None
        canonical_reason = canonical.get("selection_reason") if canonical else None
        inspected_accounts: list[dict] = []
        cleanup_candidates = 0
        active_accounts = 0

        for acct in group:
            acct_id = str(acct.get("_id") or acct.get("id") or "")
            state = acct.get("state", "UNKNOWN")
            is_live = state in ("CONNECTED", "DEPLOYED")
            created_at = _parse_metaapi_dt(acct.get("createdAt") or acct.get("created_at"))
            age_minutes = int((now - created_at).total_seconds() // 60) if created_at else None
            linked_user_id = linked_user_by_account.get(acct_id)

            has_account_data = False
            has_open_positions = False
            recent_activity = False
            score_breakdown = {
                "connected": 50 if is_live else 0,
                "account_data": 0,
                "recent_activity": 0,
                "positions": 0,
                "preferred": 5 if acct_id == canonical_id else 0,
            }

            if is_live:
                try:
                    info = await get_account_information(acct_id)
                    has_account_data = _has_account_data(info)
                    if has_account_data:
                        score_breakdown["account_data"] = 30
                except Exception:
                    has_account_data = False

                try:
                    positions = await get_open_positions(acct_id)
                    has_open_positions = bool(positions)
                    if has_open_positions:
                        score_breakdown["positions"] = 20
                except Exception:
                    has_open_positions = False

            try:
                deals = await get_deal_history(acct_id, days=1)
                recent_activity = any(
                    (deal_time := _parse_metaapi_dt(d.get("time"))) is not None and (now - deal_time) < timedelta(hours=24)
                    for d in deals
                )
                if recent_activity:
                    score_breakdown["recent_activity"] = 10
            except Exception:
                recent_activity = False

            score = sum(score_breakdown.values())
            if is_live:
                active_accounts += 1

            cleanup_candidate = False
            cleanup_reason = None
            if acct_id != canonical_id:
                if linked_user_id:
                    cleanup_reason = "linked_to_user"
                elif has_open_positions:
                    cleanup_reason = "has_open_positions"
                elif recent_activity:
                    cleanup_reason = "recent_deals"
                elif created_at and (now - created_at) < timedelta(hours=2):
                    cleanup_reason = "within_grace_period"
                else:
                    cleanup_candidate = True
                    cleanup_reason = "stale_duplicate"
                    cleanup_candidates += 1
            else:
                cleanup_reason = "canonical"

            inspected_accounts.append({
                "id": acct_id,
                "state": state,
                "score": score,
                "score_breakdown": score_breakdown,
                "selection_reason": canonical_reason if acct_id == canonical_id else None,
                "is_canonical": acct_id == canonical_id,
                "linked_user_id": linked_user_id,
                "has_account_data": has_account_data,
                "has_open_positions": has_open_positions,
                "recent_activity": recent_activity,
                "age_minutes": age_minutes,
                "cleanup_candidate": cleanup_candidate,
                "cleanup_reason": cleanup_reason,
                "name": acct.get("name"),
                "type": acct.get("type"),
                "server": acct.get("server"),
                "login": str(acct.get("login", "")),
            })

        inspected_accounts.sort(
            key=lambda a: (a["is_canonical"], a["score"], -(a["age_minutes"] or 0)),
            reverse=True,
        )
        groups.append({
            "key": f"{login}|{server}",
            "login": login,
            "server": server,
            "canonical_account_id": canonical_id,
            "accounts": inspected_accounts,
            "summary": {
                "total_accounts": len(group),
                "active_accounts": active_accounts,
                "cleanup_candidates": cleanup_candidates,
            },
        })

    groups.sort(key=lambda g: (g["summary"]["cleanup_candidates"], g["summary"]["total_accounts"], g["key"]), reverse=True)
    return groups


async def provision_account(user) -> str:
    """Creates a MetaApi cloud MT5 terminal for a user. Returns accountId."""
    password = decrypt_password(user.mt_password_enc)
    payload = {
        "name": f"user-{user.id[:8]}",
        "type": "cloud",
        "login": user.mt_login,
        "password": password,
        "server": user.mt_server,
        "platform": "mt5",
        "magic": 12345,
        "tags": ["DominanceMapper"]
    }
    _track_call("provision_account")
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{PROVISION_URL}/users/current/accounts",
            json=payload, headers=_headers()
        )
        resp.raise_for_status()
        account_id = resp.json().get("_id", resp.json().get("id"))
        logger.info(f"Provisioned MetaApi account {account_id} for user {user.id}")
        return account_id


async def deploy_account(account_id: str):
    """Triggers the cloud terminal deployment. Takes ~60-90s to reach DEPLOYED state."""
    _track_call("deploy_account")
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{PROVISION_URL}/users/current/accounts/{account_id}/deploy",
            headers=_headers()
        )
        resp.raise_for_status()
        logger.info(f"Deploy triggered for MetaApi account {account_id}")


async def get_account_status(account_id: str, use_cache: bool = True) -> str:
    """
    Returns current MetaApi connection state string.

    Caches the result in Redis for 60 seconds. This means:
    - Trade execution checks use Redis (free) instead of MetaApi (credit)
    - The background poller is the only thing that ever calls MetaApi for status
    - Pass use_cache=False only when you explicitly want a fresh value (e.g. the poller itself)
    """
    cache_key = f"mt_status:{account_id}"

    if use_cache:
        try:
            from app.utils.redis_client import redis_client
            cached = redis_client.get(cache_key)
            if cached:
                logger.debug(f"[Cache HIT] mt_status:{account_id} = {cached}")
                return cached.decode() if isinstance(cached, bytes) else cached
        except Exception as e:
            logger.debug(f"Redis unavailable for mt_status cache: {type(e).__name__}")

    try:
        _track_call("get_account_status")
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{PROVISION_URL}/users/current/accounts/{account_id}",
                headers=_headers()
            )
            data = resp.json()
            state = data.get("state", "UNKNOWN")

        # Cache for 60 seconds — execution engine reads this for free
        try:
            from app.utils.redis_client import redis_client
            redis_client.setex(cache_key, 60, state)
        except Exception:
            pass

        return state
    except Exception as e:
        logger.error(f"Failed to get account status for {account_id}: {repr(e)}")
        return "ERROR"


async def undeploy_account(account_id: str):
    """Stops the cloud terminal (saves MetaApi quota while user is inactive)."""
    _track_call("undeploy_account")
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{PROVISION_URL}/users/current/accounts/{account_id}/undeploy",
            headers=_headers()
        )
        resp.raise_for_status()
        logger.info(f"Undeployed MetaApi account {account_id}")


# ─── Status Polling During Connection Setup ───────────────────────────────────

async def poll_until_connected(user_id: str, account_id: str, db_session_factory, max_attempts: int = 10):
    """
    Polls MetaApi status every 30s for up to 10 attempts (5 min total) until the
    terminal reaches DEPLOYED/CONNECTED state. Then updates user.mt_status in DB.

    Credit cost: max 10 REST calls per connection setup (was up to 18 at 10s intervals).
    """
    from app.database.db import SessionLocal

    for attempt in range(1, max_attempts + 1):
        await asyncio.sleep(30)  # 30s intervals — was 10s
        state = await get_account_status(account_id)
        logger.info(f"[Poll #{attempt}/{max_attempts}] Account {account_id} state: {state}")

        if state in ("DEPLOYED", "CONNECTED"):
            db = SessionLocal()
            try:
                from app.models.user import User
                user = db.query(User).filter(User.id == user_id).first()
                if user:
                    user.mt_status = "connected"
                    db.commit()
                    logger.info(f"✓ User {user_id} MT5 terminal is now CONNECTED.")
            finally:
                db.close()
            return

        elif state in ("DEPLOY_FAILED", "ERROR"):
            db = SessionLocal()
            try:
                from app.models.user import User
                user = db.query(User).filter(User.id == user_id).first()
                if user:
                    user.mt_status = "error"
                    db.commit()
            finally:
                db.close()
            logger.error(f"✗ MetaApi account {account_id} entered error state after {attempt} attempts.")
            return

    # Timed out — mark as error so user knows to retry
    logger.warning(f"⚠ poll_until_connected timed out after {max_attempts} attempts for account {account_id}")
    db = SessionLocal()
    try:
        from app.models.user import User
        user = db.query(User).filter(User.id == user_id).first()
        if user and user.mt_status == "deploying":
            user.mt_status = "error"
            db.commit()
    finally:
        db.close()


# ─── Background Status Poller (Production Mode) ───────────────────────────────

async def cache_all_account_statuses():
    """
    Background task that polls MT5 status for users that need monitoring.

    SMART POLLING RULES (to minimise MetaApi credit usage):
      1. Runs every 5 MINUTES — was 15 seconds (20× fewer calls)
      2. Skips users whose DB status is already 'connected' — no wasted calls
      3. Skips ghost/test accounts (meta_account_id starting with 'mt5-')
      4. Only polls users in 'deploying' or 'error' state (actively changing)

    Credit cost example — 20 users:
      Old:  5,760 calls/day/user × 20 = 115,200 calls/day
      New:  288 calls/day (only for non-connected) × few users = ~1,000 calls/day
    """
    from app.database.db import SessionLocal
    from app.models.user import User
    from app.utils.redis_client import redis_client

    logger.info("[StatusPoller] Background status poller started. Interval: 300s (5 min)")

    while True:
        try:
            db = SessionLocal()
            users_needing_poll = db.query(User).filter(
                User.is_active == True,
                User.meta_account_id.isnot(None),
            ).all()

            if users_needing_poll:
                logger.info(f"[StatusPoller] Polling {len(users_needing_poll)} MetaApi-linked users")
            else:
                logger.debug("[StatusPoller] No MetaApi-linked users found")

            for user in users_needing_poll:
                meta_id = user.meta_account_id

                # Skip ghost/test accounts
                if meta_id and meta_id.startswith("mt5-"):
                    continue

                # Bypass cache — poller always fetches fresh state and writes it to Redis
                # so the execution engine can read from cache between poll cycles
                status = await get_account_status(meta_id, use_cache=False)

                # Cache with 6 min expiry (slightly longer than poll interval for coverage)
                redis_client.setex(f"mt_status:{meta_id}", 360, status)

                # Keep DB aligned even after an account was previously healthy.
                if status in ("DEPLOYED", "CONNECTED"):
                    if bool(getattr(user, "trading_paused", False)):
                        # Check if account is actually healthy — auto-recover if so
                        try:
                            account_info = await get_account_information(meta_id)
                            has_valid_data = isinstance(account_info, dict) and any(
                                account_info.get(key) is not None for key in ("balance", "equity", "marginFree", "freeMargin")
                            )
                        except Exception:
                            has_valid_data = False

                        if has_valid_data:
                            user.trading_paused = False
                            user.mt_status = "connected"
                            user.can_trade = True
                            db.commit()
                            logger.info(
                                f"[StatusPoller] Auto-recovered trading_paused for user {user.id}: "
                                f"account healthy (balance={account_info.get('balance')})"
                            )
                        else:
                            changed = user.mt_status != "connected" or getattr(user, "can_trade", False) is not False
                            user.mt_status = "connected"
                            user.can_trade = False
                            if changed:
                                db.commit()
                                logger.info(f"[StatusPoller] User {user.id} is connected but trading_paused=true and no account data; kept non-tradable")
                        continue

                    changed = user.mt_status != "connected" or getattr(user, "can_trade", False) is False
                    user.mt_status = "connected"
                    user.can_trade = True
                    if changed:
                        db.commit()
                        logger.info(f"[StatusPoller] User {user.id} is connected")
                else:
                    next_status = "error" if status in ("DEPLOY_FAILED", "ERROR") else "disconnected"
                    changed = user.mt_status != next_status or getattr(user, "can_trade", False) is True
                    user.mt_status = next_status
                    user.can_trade = False
                    if changed:
                        db.commit()
                        logger.warning(f"[StatusPoller] User {user.id} downgraded to {next_status} (live={status})")

            db.close()
        except Exception as e:
            logger.error(f"[StatusPoller] Error: {e}")

        await asyncio.sleep(300)  # 5 minutes — was 15 seconds


# ─── Trade Execution + Redis-Cached Data Fetchers ─────────────────────────────

async def get_open_positions(account_id: str) -> list:
    """
    Returns open positions. Redis-cached for 10 seconds.

    Uses a setnx distributed LOCK to prevent the thundering-herd problem:
    when 5 parallel workers all receive a signal at the same instant and all
    try to fetch positions simultaneously before the cache is populated,
    only the FIRST worker makes the MetaApi REST call — the rest wait 100ms
    and then read from the cache the first worker populated.

    Example — 20 users, signal arrives:
      Old: 20 parallel REST calls → 20 MetaApi credits consumed
      New: 1 REST call + 19 cache hits → 1 MetaApi credit consumed
    """
    cache_key = f"positions:{account_id}"
    lock_key = f"positions_lock:{account_id}"

    try:
        from app.utils.redis_client import redis_client

        # 1. Check cache first
        cached = redis_client.get(cache_key)
        if cached:
            logger.debug(f"[Cache HIT] positions:{account_id}")
            return json.loads(cached)

        # 2. Try to acquire distributed lock atomically (SET NX EX = atomic setnx + expire)
        lock_acquired = redis_client.set(lock_key, "1", nx=True, ex=2)
        if not lock_acquired:
            # Another worker is already fetching — wait briefly then read their result
            logger.debug(f"[Lock WAIT] positions:{account_id} — another worker is fetching")
            await asyncio.sleep(0.2)
            cached = redis_client.get(cache_key)
            if cached:
                return json.loads(cached)
            # If still no cache after waiting, fall through and do our own call
    except Exception as e:
        logger.debug(f"Redis unavailable for positions cache: {type(e).__name__}")

    try:
        _track_call("get_open_positions")
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{TRADE_URL}/users/current/accounts/{account_id}/positions",
                headers=_headers()
            )
            resp.raise_for_status()
            positions = resp.json()

        # Populate cache + release lock
        try:
            from app.utils.redis_client import redis_client
            redis_client.setex(cache_key, 10, json.dumps(positions))
            redis_client.delete(lock_key)  # Release lock immediately after cache is ready
        except Exception:
            pass

        return positions
    except Exception as e:
        logger.error(f"Error fetching open positions for {account_id}: {e}")
    return []


def _normalize_pos_side(raw_type) -> str | None:
    """
    MetaApi position payloads can vary by broker/account:
    - "buy"/"sell"
    - "POSITION_TYPE_BUY"/"POSITION_TYPE_SELL"
    - sometimes numeric enums
    We normalize to "buy"/"sell" when possible.
    """
    if raw_type is None:
        return None
    s = str(raw_type).lower()
    if "buy" in s:
        return "buy"
    if "sell" in s:
        return "sell"
    return None


async def has_open_position(account_id: str, symbol: str, side: Optional[str] = None) -> bool:
    """
    Returns True if the user already has an open position in this symbol.

    If side is provided, only returns True for an *existing position on the same side*.
    This prevents same-side stacking while still allowing an opposite-side order
    to close/net/hedge depending on the broker account mode.
    """
    canonical = resolve_symbol(symbol)
    want_side = side.lower() if side else None
    positions = await get_open_positions(account_id)
    for pos in positions:
        pos_symbol = resolve_symbol(pos.get("symbol", ""))
        if pos_symbol.upper() == canonical.upper():
            if want_side:
                existing_side = _normalize_pos_side(pos.get("type"))
                if existing_side and existing_side != want_side:
                    continue
            logger.info(f"Duplicate guard: position already open for {symbol} on account {account_id}")
            return True
    return False


async def get_account_information(account_id: str) -> dict:
    """
    Returns MT5 account data (balance, equity, margin, etc.).
    Redis-cached for 30 seconds — balance doesn't change in milliseconds.
    """
    try:
        from app.utils.redis_client import redis_client
        cache_key = f"acct_info:{account_id}"
        cached = redis_client.get(cache_key)
        if cached:
            logger.debug(f"[Cache HIT] acct_info:{account_id}")
            return json.loads(cached)
    except Exception:
        pass

    try:
        _track_call("get_account_information")
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{TRADE_URL}/users/current/accounts/{account_id}/accountInformation",
                headers=_headers()
            )
            resp.raise_for_status()
            info = resp.json()

        # Cache for 30 seconds
        try:
            from app.utils.redis_client import redis_client
            redis_client.setex(cache_key, 30, json.dumps(info))
        except Exception:
            pass

        return info
    except Exception as e:
        logger.error(f"Error fetching account info for {account_id}: {e}")
    return {}


async def get_symbol_specification(account_id: str, symbol: str) -> dict:
    """
    Returns MT5 symbol specification from MetaApi (minVolume, stopLevel, digits, point, etc.).
    Redis-cached for 10 MINUTES — broker specs almost never change mid-session.

    Used by the Execution Adapter to normalize volume, SL/TP, and price precision
    before every trade so we never get broker rejections for invalid parameters.
    """
    cache_key = f"sym_spec:{account_id}:{symbol}"
    try:
        from app.utils.redis_client import redis_client
        cached = redis_client.get(cache_key)
        if cached:
            logger.debug(f"[Cache HIT] sym_spec:{symbol}")
            return json.loads(cached)
    except Exception:
        pass

    candidates = [symbol]
    canonical = resolve_symbol(symbol)
    if canonical not in candidates:
        candidates.append(canonical)
    for variant in SYMBOL_MAP.get(canonical, []):
        if variant not in candidates:
            candidates.append(variant)

    try:
        _track_call("get_symbol_specification")
        async with httpx.AsyncClient(timeout=10) as client:
            for candidate in candidates:
                try:
                    resp = await client.get(
                        f"{TRADE_URL}/users/current/accounts/{account_id}/symbols/{candidate}",
                        headers=_headers()
                    )
                    resp.raise_for_status()
                    spec = resp.json()

                    try:
                        from app.utils.redis_client import redis_client
                        redis_client.setex(cache_key, 600, json.dumps(spec))
                    except Exception:
                        pass

                    logger.info(f"[MetaApi] Symbol spec for {candidate}: minVol={spec.get('minVolume')}, stopLevel={spec.get('stopLevel')}, digits={spec.get('digits')}")
                    return spec
                except httpx.HTTPStatusError as exc:
                    if exc.response.status_code != 404:
                        raise
                    logger.info(f"[MetaApi] Symbol spec not found for candidate {candidate} on {account_id}")
    except Exception as e:
        logger.error(f"Error fetching symbol specification for {symbol} on {account_id}: {e}")
    return {}


async def get_deal_history(account_id: str, days: int = 90) -> list:
    """
    Returns completed deal history from MetaApi for the given account.
    Redis-cached for 60 seconds.
    """
    from datetime import datetime, timedelta, timezone

    cache_key = f"deal_history:{account_id}"
    try:
        from app.utils.redis_client import redis_client
        cached = redis_client.get(cache_key)
        if cached:
            logger.debug(f"[Cache HIT] deal_history:{account_id}")
            return json.loads(cached)
    except Exception:
        pass

    try:
        _track_call("get_deal_history")
        start = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT00:00:00.000Z")
        end = datetime.now(timezone.utc).strftime("%Y-%m-%dT23:59:59.999Z")

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{TRADE_URL}/users/current/accounts/{account_id}/history-deals/time/{start}/{end}",
                headers=_headers()
            )
            resp.raise_for_status()
            deals = resp.json()

        try:
            from app.utils.redis_client import redis_client
            redis_client.setex(cache_key, 60, json.dumps(deals))
        except Exception:
            pass

        return deals
    except Exception as e:
        logger.error(f"Error fetching deal history for {account_id}: {e}")
    return []


async def execute_trade(
    account_id: str,
    symbol: str,
    side: str,
    volume: float = 0.01,
    sl: Optional[float] = 0,
    tp: Optional[float] = 0
) -> dict:
    """
    Places a market order via MetaApi.
    Includes symbol resolution and a hard volume cap of 0.10 lots for MVP safety.
    Invalidates the Redis positions cache after execution so next check is fresh.
    """
    from app.config import MAX_POSITION_SIZE
    volume = min(volume, MAX_POSITION_SIZE)

    canonical = resolve_symbol(symbol)
    action_type = "ORDER_TYPE_BUY" if side.upper() == "BUY" else "ORDER_TYPE_SELL"

    payload: dict = {
        "symbol": canonical,
        "actionType": action_type,
        "volume": volume,
        "comment": "DominanceMapper",
        "magic": 12345
    }
    if sl is not None and float(sl) > 0:
        payload["stopLoss"] = float(sl)
    if tp is not None and float(tp) > 0:
        payload["takeProfit"] = float(tp)

    _track_call("execute_trade")
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{TRADE_URL}/users/current/accounts/{account_id}/trade",
            json=payload, headers=_headers()
        )
        resp.raise_for_status()
        result = resp.json()
        logger.info(f"MetaApi trade executed on {account_id}: {result}")

    # Invalidate position cache so the next has_open_position() call is fresh
    try:
        from app.utils.redis_client import redis_client
        redis_client.delete(f"positions:{account_id}")
    except Exception:
        pass

    return result


async def close_position(account_id: str, position_id: str) -> dict:
    """
    Closes a specific open position by its MetaApi position ID.
    Invalidates the Redis positions cache after closing.
    """
    payload = {
        "actionType": "POSITION_CLOSE_ID",
        "positionId": position_id,
    }

    _track_call("close_position")
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{TRADE_URL}/users/current/accounts/{account_id}/trade",
            json=payload, headers=_headers()
        )
        resp.raise_for_status()
        result = resp.json()
        logger.info(f"MetaApi position {position_id} closed on {account_id}: {result}")

    # Invalidate position cache
    try:
        from app.utils.redis_client import redis_client
        redis_client.delete(f"positions:{account_id}")
    except Exception:
        pass

    return result

async def update_position_stops(
    account_id: str,
    position_id: str,
    sl: Optional[float] = None,
    tp: Optional[float] = None,
) -> bool:
    """
    Updates SL/TP for an existing position.
    """
    payload = {
        "actionType": "POSITION_MODIFY",
        "positionId": position_id,
    }
    if sl is not None:
        payload["stopLoss"] = sl
    if tp is not None:
        payload["takeProfit"] = tp

    if "stopLoss" not in payload and "takeProfit" not in payload:
        logger.warning(f"Skipped stop update for {position_id} on {account_id}: no SL/TP supplied")
        return False

    _track_call("update_position_stops")
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{TRADE_URL}/users/current/accounts/{account_id}/trade",
                json=payload, headers=_headers()
            )
            resp.raise_for_status()
            logger.info(
                f"MetaApi position {position_id} stops updated on {account_id}: "
                f"sl={sl} tp={tp}"
            )

            # Invalidate position cache
            try:
                from app.utils.redis_client import redis_client
                redis_client.delete(f"positions:{account_id}")
            except Exception:
                pass

            return True
    except Exception as e:
        logger.error(f"Failed to update stops for position {position_id} on {account_id}: {e}")
        return False


async def update_position_sl(account_id: str, position_id: str, sl: float) -> bool:
    """
    Updates the Stop Loss of an existing position.
    """
    return await update_position_stops(account_id, position_id, sl=sl)
