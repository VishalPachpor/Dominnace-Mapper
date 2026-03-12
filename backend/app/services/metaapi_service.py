"""
MetaApi Cloud MT5 Service Layer
Handles account provisioning, deployment, status polling, and trade execution.
"""
import os
import asyncio
import logging
import httpx
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
    "XAGUSD": ["XAGUSD", "XAGUSDm"],
}


def _headers() -> dict:
    token = os.environ.get("META_API_TOKEN")
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


# ─── Account Lifecycle ────────────────────────────────────────────────────────

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
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{PROVISION_URL}/users/current/accounts",
            json=payload, headers=_headers()
        )
        resp.raise_for_status()
        account_id = resp.json()["id"]
        logger.info(f"Provisioned MetaApi account {account_id} for user {user.id}")
        return account_id


async def deploy_account(account_id: str):
    """Triggers the cloud terminal deployment. Takes ~60-90s to reach DEPLOYED state."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{PROVISION_URL}/users/current/accounts/{account_id}/deploy",
            headers=_headers()
        )
        resp.raise_for_status()
        logger.info(f"Deploy triggered for MetaApi account {account_id}")


async def get_account_status(account_id: str) -> str:
    """Returns current MetaApi connection state string."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{PROVISION_URL}/users/current/accounts/{account_id}",
                headers=_headers()
            )
            data = resp.json()
            return data.get("state", "UNKNOWN")
    except Exception as e:
        logger.error(f"Failed to get account status for {account_id}: {e}")
        return "ERROR"


async def undeploy_account(account_id: str):
    """Stops the cloud terminal (saves MetaApi quota while user is inactive)."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{PROVISION_URL}/users/current/accounts/{account_id}/undeploy",
            headers=_headers()
        )
        resp.raise_for_status()
        logger.info(f"Undeployed MetaApi account {account_id}")


# ─── Status Polling Background Task ──────────────────────────────────────────

async def poll_until_connected(user_id: str, account_id: str, db_session_factory, max_wait: int = 180):
    """
    Polls MetaApi status every 10s until DEPLOYED, then updates user.mt_status = 'connected'.
    Runs as a background asyncio task — does NOT block the API response.
    """
    from app.database.db import SessionLocal
    elapsed = 0
    while elapsed < max_wait:
        await asyncio.sleep(10)
        elapsed += 10
        state = await get_account_status(account_id)
        logger.info(f"[Poll] Account {account_id} state: {state} ({elapsed}s elapsed)")
        if state in ("DEPLOYED", "CONNECTED"):
            db = SessionLocal()
            try:
                from app.models.user import User
                user = db.query(User).filter(User.id == user_id).first()
                if user:
                    user.mt_status = "connected"
                    db.commit()
                    logger.info(f"User {user_id} MT5 terminal is now CONNECTED.")
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
            logger.error(f"MetaApi account {account_id} entered error state.")
            return
    logger.warning(f"Timed out waiting for account {account_id} to deploy.")


# ─── Trade Execution ──────────────────────────────────────────────────────────

async def has_open_position(account_id: str, symbol: str) -> bool:
    """Returns True if the user already has an open position in this symbol."""
    try:
        canonical = resolve_symbol(symbol)
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{TRADE_URL}/users/current/accounts/{account_id}/positions",
                headers=_headers()
            )
            positions = resp.json()
            for pos in positions:
                pos_symbol = resolve_symbol(pos.get("symbol", ""))
                if pos_symbol.upper() == canonical.upper():
                    logger.info(f"Duplicate guard: position already open for {symbol} on account {account_id}")
                    return True
    except Exception as e:
        logger.error(f"Error checking open positions: {e}")
    return False


async def execute_trade(
    account_id: str,
    symbol: str,
    side: str,
    volume: float = 0.01,
    sl: float = 0,
    tp: float = 0
) -> dict:
    """
    Places a market order via MetaApi.
    Includes symbol resolution and a hard volume cap of 0.10 lots for MVP safety.
    """
    # Volume safety cap
    MAX_VOLUME = 0.10
    volume = min(volume, MAX_VOLUME)

    canonical = resolve_symbol(symbol)
    action_type = "ORDER_TYPE_BUY" if side.upper() == "BUY" else "ORDER_TYPE_SELL"

    payload: dict = {
        "symbol": canonical,
        "actionType": action_type,
        "volume": volume,
        "comment": "DominanceMapper",
        "magic": 12345
    }
    if sl > 0:
        payload["stopLoss"] = sl
    if tp > 0:
        payload["takeProfit"] = tp

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{TRADE_URL}/users/current/accounts/{account_id}/trade",
            json=payload, headers=_headers()
        )
        resp.raise_for_status()
        result = resp.json()
        logger.info(f"MetaApi trade executed on {account_id}: {result}")
        return result
