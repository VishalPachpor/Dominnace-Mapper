from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.database.db import get_db
from app.utils.security import get_current_user
from app.services.trade_closer import force_close_orphaned_trades_for_user
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


async def _refresh_user_mt_state(user, db: Session):
    """
    Reconcile the stored user MT status with live MetaApi state so the UI does not
    trust stale `connected` flags after broker/demo expiry.
    """
    meta_account_id = getattr(user, "meta_account_id", None)
    if not meta_account_id:
        if user.mt_status != "disconnected" or getattr(user, "can_trade", False):
            user.mt_status = "disconnected"
            user.can_trade = False
            db.commit()
        return user

    try:
        from app.services.metaapi_service import get_account_status, get_account_information, find_existing_account

        live_status = await get_account_status(meta_account_id, use_cache=False)
        if live_status in ("CONNECTED", "DEPLOYED"):
            # If trading_paused, check if account is actually healthy and auto-recover
            if bool(getattr(user, "trading_paused", False)):
                account_info = await get_account_information(meta_account_id)
                has_valid_data = isinstance(account_info, dict) and any(
                    account_info.get(key) is not None for key in ("balance", "equity", "marginFree", "freeMargin")
                )
                if has_valid_data:
                    # Account is live with real data — the transient pause reason no longer applies
                    old_account_id = getattr(user, "meta_account_id", None)
                    user.trading_paused = False
                    user.mt_status = "connected"
                    user.can_trade = True
                    db.commit()
                    logger.info(
                        "metaapi_rebind %s",
                        {
                            "user_id": user.id,
                            "old_account_id": old_account_id,
                            "new_account_id": user.meta_account_id,
                            "login": user.mt_login,
                            "server": user.mt_server,
                            "reason": "healthy_account_data_auto_recover",
                        },
                        extra={
                            "user_id": user.id,
                            "old_account_id": old_account_id,
                            "new_account_id": user.meta_account_id,
                            "login": user.mt_login,
                            "server": user.mt_server,
                            "reason": "healthy_account_data_auto_recover",
                        }
                    )
                    logger.info(
                        f"Auto-recovered trading_paused for user {user.id}: "
                        f"account healthy (balance={account_info.get('balance')}, equity={account_info.get('equity')})"
                    )
                    return user
                else:
                    # Paused AND no account data — stay non-tradable
                    changed = user.mt_status != "connected" or getattr(user, "can_trade", False) is not False
                    user.mt_status = "connected"
                    user.can_trade = False
                    if changed:
                        db.commit()
                        logger.info(f"MT connected but trading_paused=true and no account data for user {user.id}; keeping non-tradable")
                    return user

            account_info = await get_account_information(meta_account_id)
            has_account_data = isinstance(account_info, dict) and any(
                account_info.get(key) is not None for key in ("balance", "equity", "marginFree", "freeMargin")
            )
            if not has_account_data:
                # The linked MetaApi terminal may be a stale duplicate. Try to switch
                # the user to a healthier sibling account for the same MT5 login/server.
                if getattr(user, "mt_login", None) and getattr(user, "mt_server", None):
                    replacement = await find_existing_account(
                        user.mt_login,
                        user.mt_server,
                        preferred_account_id=meta_account_id,
                    )
                    replacement_id = replacement.get("account_id") if replacement else None
                    if replacement_id and replacement_id != meta_account_id:
                        old_account_id = meta_account_id
                        user.meta_account_id = replacement_id
                        meta_account_id = replacement_id
                        live_status = await get_account_status(meta_account_id, use_cache=False)
                        account_info = await get_account_information(meta_account_id)
                        has_account_data = isinstance(account_info, dict) and any(
                            account_info.get(key) is not None for key in ("balance", "equity", "marginFree", "freeMargin")
                        )
                        logger.info(
                            "metaapi_rebind %s",
                            {
                                "user_id": user.id,
                                "old_account_id": old_account_id,
                                "new_account_id": replacement_id,
                                "login": user.mt_login,
                                "server": user.mt_server,
                                "reason": "health_score",
                            },
                            extra={
                                "user_id": user.id,
                                "old_account_id": old_account_id,
                                "new_account_id": replacement_id,
                                "login": user.mt_login,
                                "server": user.mt_server,
                                "reason": "health_score",
                            }
                        )
                        logger.info(
                            f"Switched user {user.id} to healthier MetaApi account {replacement_id} "
                            f"for login={user.mt_login}"
                        )

            if not has_account_data:
                changed = user.mt_status != "connected" or getattr(user, "can_trade", False) is not False
                user.mt_status = "connected"
                user.can_trade = False
                if changed:
                    db.commit()
                    logger.warning(
                        f"MT terminal connected but account info unavailable for user {user.id}; marked non-tradable"
                    )
                return user

            if user.mt_status != "connected" or not getattr(user, "can_trade", False):
                user.mt_status = "connected"
                user.can_trade = True
                db.commit()
            return user

        # Any non-live broker state means the account should not be tradable.
        if getattr(user, "mt_login", None) and getattr(user, "mt_server", None):
            replacement = await find_existing_account(
                user.mt_login,
                user.mt_server,
                preferred_account_id=meta_account_id,
            )
            replacement_id = replacement.get("account_id") if replacement else None
            replacement_state = replacement.get("state") if replacement else None
            if replacement_id and replacement_id != meta_account_id and replacement_state in ("CONNECTED", "DEPLOYED"):
                old_account_id = meta_account_id
                user.meta_account_id = replacement_id
                user.mt_status = "connected"
                user.can_trade = True
                user.trading_paused = False
                db.commit()
                logger.info(
                    "metaapi_rebind %s",
                    {
                        "user_id": user.id,
                        "old_account_id": old_account_id,
                        "new_account_id": replacement_id,
                        "login": user.mt_login,
                        "server": user.mt_server,
                        "reason": "recover_from_stale_terminal",
                    },
                    extra={
                        "user_id": user.id,
                        "old_account_id": old_account_id,
                        "new_account_id": replacement_id,
                        "login": user.mt_login,
                        "server": user.mt_server,
                        "reason": "recover_from_stale_terminal",
                    }
                )
                logger.info(
                    f"Recovered user {user.id} from stale MetaApi account {meta_account_id} "
                    f"to healthy sibling {replacement_id}"
                )
                return user

        user.mt_status = "error" if live_status in ("DEPLOY_FAILED", "ERROR") else "disconnected"
        user.can_trade = False
        closed_count = force_close_orphaned_trades_for_user(
            db, user.id, close_reason=f"ACCOUNT_STATE_{live_status or 'UNKNOWN'}"
        )
        db.commit()
        logger.warning(
            f"MT state resynced for user {user.id}: live_status={live_status}, force_closed_trades={closed_count}"
        )
    except Exception as e:
        logger.warning(f"Could not refresh MT state for user {user.id}: {e}")

    return user


def _safe_last4(encrypted_val: str | None) -> str | None:
    """Decrypt an encrypted API key and return only the last 4 chars for display."""
    if not encrypted_val:
        return None
    try:
        from app.utils.crypto_util import decrypt_password
        plain = decrypt_password(encrypted_val)
        return plain[-4:] if len(plain) >= 4 else plain
    except Exception:
        return "****"


class AddApiKeyRequest(BaseModel):
    api_key: str
    secret_key: str

@router.post("/add-api-key")
def save_api_keys(data: AddApiKeyRequest, user=Depends(get_current_user), db: Session = Depends(get_db)):
    from app.utils.crypto_util import encrypt_password
    user.exchange_api_key = encrypt_password(data.api_key)
    user.exchange_secret_key = encrypt_password(data.secret_key)
    db.commit()
    return {"message": "API keys saved successfully"}

@router.post("/ea-token")
def generate_ea_token(user=Depends(get_current_user), db: Session = Depends(get_db)):
    import uuid
    user.ea_token = str(uuid.uuid4())
    db.commit()
    return {"message": "EA Token generated", "ea_token": user.ea_token}

@router.get("/ea-token")
def get_ea_token(user=Depends(get_current_user)):
    return {
        "ea_token": user.ea_token,
        "ea_last_seen": user.ea_last_seen
    }

@router.get("/me")
async def get_user_profile(user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Return the user's profile information, API keys, and notification settings."""
    user = await _refresh_user_mt_state(user, db)
    return {
        "email": user.email,
        "full_name": user.full_name or "",
        "avatar_url": user.avatar_url or "",
        "oauth_provider": None,
        "bio": "",  # TODO: add bio column to users table
        "telegram_alerts": True,
        "push_notifications": False,
        # API Keys Status
        "has_binance_key": bool(user.exchange_api_key),
        "binance_api_key_last4": _safe_last4(user.exchange_api_key),
        "has_mt5_key": bool(user.meta_account_id),
        "mt_login": user.mt_login,
        "mt_server": user.mt_server,
        "mt_broker": user.mt_broker,
        "mt_status": user.mt_status,
        "can_trade": bool(getattr(user, "can_trade", False)),
        "ea_token_active": bool(user.ea_token)
    }

class UpdatePasswordRequest(BaseModel):
    password: str

@router.put("/me/password")
def update_password(data: UpdatePasswordRequest, user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Update the user's password (email/password accounts only)."""
    from app.utils.security import hash_password
    if not user.password_hash:
        raise HTTPException(status_code=400, detail="OAuth accounts cannot set a password here.")
    if len(data.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters.")
    user.password_hash = hash_password(data.password)
    db.commit()
    return {"message": "Password updated successfully"}

class UpdateProfileRequest(BaseModel):
    full_name: str | None = None
    avatar_url: str | None = None
    bio: str | None = None
    telegram_alerts: bool | None = None
    push_notifications: bool | None = None

@router.put("/me")
def update_user_profile(data: UpdateProfileRequest, user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Save editable profile fields."""
    if data.full_name is not None:
        user.full_name = data.full_name
    if data.avatar_url is not None:
        user.avatar_url = data.avatar_url
    db.commit()
    return {"message": "Profile updated successfully"}

@router.delete("/api-key/binance")
def delete_binance_key(user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Revoke Binance API keys."""
    user.exchange_api_key = None
    user.exchange_secret_key = None
    db.commit()
    return {"message": "Binance API keys revoked"}

@router.delete("/api-key/mt5")
async def delete_mt5_key(user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Revoke MT5 Connection and undeploy the MetaApi terminal."""
    # Undeploy the MetaApi terminal to free resources and prevent orphaned terminals
    old_account_id = getattr(user, "meta_account_id", None)
    if old_account_id:
        try:
            from app.services.metaapi_service import undeploy_account
            await undeploy_account(old_account_id)
            logger.info(f"Undeployed MetaApi terminal {old_account_id} for user {user.id}")
        except Exception as e:
            logger.warning(f"Failed to undeploy MetaApi terminal {old_account_id}: {e}")

    user.mt_login = None
    user.mt_password_enc = None
    user.mt_server = None
    user.mt_broker = None
    user.meta_account_id = None
    user.mt_status = "disconnected"
    user.trading_paused = False
    user.can_trade = False
    closed_count = force_close_orphaned_trades_for_user(
        db, user.id, close_reason="ACCOUNT_DISCONNECTED"
    )
    db.commit()
    return {"message": "MT5 connection revoked", "force_closed_trades": closed_count}

@router.get("/")
def get_users(user=Depends(get_current_user)):
    return {"message": "Users endpoint"}


# ─── MetaApi MT5 Connection Endpoints ────────────────────────────────────────

class MT5ConnectRequest(BaseModel):
    mt_login: str
    mt_password: str
    mt_server: str
    mt_broker: str

@router.post("/connect-mt5")
async def connect_mt5(
    req: MT5ConnectRequest,
    background_tasks: BackgroundTasks,
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Provisions a MetaApi cloud MT5 terminal for the authenticated user.
    Broker password is Fernet-encrypted before storage.
    Deployment is async — status transitions: connecting → deploying → connected.
    """
    from app.utils.crypto_util import encrypt_password
    from app.services.metaapi_service import (
        provision_account, deploy_account, poll_until_connected, find_existing_account
    )

    # 1. Save encrypted broker credentials
    user.mt_login = req.mt_login
    user.mt_password_enc = encrypt_password(req.mt_password)
    user.mt_server = req.mt_server
    user.mt_broker = req.mt_broker
    user.mt_status = "connecting"
    user.trading_paused = False
    user.can_trade = True
    db.commit()

    # 2. Check for existing MetaApi account (prevent duplicates)
    existing = await find_existing_account(
        req.mt_login,
        req.mt_server,
        preferred_account_id=getattr(user, "meta_account_id", None),
    )
    if existing:
        account_id = existing["account_id"]
        logger.info(f"Reusing existing MetaApi account {account_id} for user {user.id}")
        user.meta_account_id = account_id

        # Ensure it's deployed
        if existing["state"] not in ("DEPLOYED", "CONNECTED"):
            user.mt_status = "deploying"
            db.commit()
            try:
                await deploy_account(account_id)
            except Exception as e:
                logger.warning(f"Deploy call failed on reused account (may still be starting): {e}")
            background_tasks.add_task(poll_until_connected, user.id, account_id, None)
            return {
                "message": "MT5 terminal is redeploying (reused existing account). Ready in ~90 seconds.",
                "account_id": account_id,
                "status": "deploying"
            }
        else:
            user.mt_status = "connected"
            user.can_trade = True
            db.commit()
            return {
                "message": "MT5 terminal reconnected (reused existing account).",
                "account_id": account_id,
                "status": "connected"
            }

    # 3. Provision new cloud account
    try:
        account_id = await provision_account(user)
        user.meta_account_id = account_id
        user.mt_status = "deploying"
        db.commit()
    except Exception as e:
        user.mt_status = "error"
        db.commit()
        error_msg = str(e)
        import httpx
        if isinstance(e, httpx.HTTPStatusError):
            try:
                error_msg = e.response.json().get("message", e.response.text)
            except Exception:
                error_msg = e.response.text
        elif isinstance(e, httpx.ReadTimeout):
            error_msg = "MetaApi timed out validating your broker credentials. The server might be unreachable or the credentials may be incorrect."

        logger.error(f"MetaApi provisioning failed for user {user.id}: {error_msg}")
        raise HTTPException(status_code=500, detail=f"MetaApi provisioning failed: {error_msg}")

    # 4. Trigger deploy
    try:
        await deploy_account(account_id)
    except Exception as e:
        logger.warning(f"Deploy call failed (terminal may still be starting): {e}")

    # 4. Start background polling — will update mt_status to 'connected' when ready
    background_tasks.add_task(poll_until_connected, user.id, account_id, None)

    return {
        "message": "MT5 terminal is deploying. Ready in ~90 seconds.",
        "account_id": account_id,
        "status": "deploying"
    }


@router.get("/mt-status")
async def get_mt_status(user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Returns the current MetaApi connection status for the authenticated user."""
    user = await _refresh_user_mt_state(user, db)
    return {
        "mt_status": getattr(user, "mt_status", "disconnected"),
        "mt_broker": getattr(user, "mt_broker", None),
        "mt_server": getattr(user, "mt_server", None),
        "mt_login": getattr(user, "mt_login", None),
        "meta_account_id": getattr(user, "meta_account_id", None),
        "can_trade": bool(getattr(user, "can_trade", False)),
    }
