from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.database.db import get_db
from app.utils.security import get_current_user
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


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
def get_user_profile(user=Depends(get_current_user)):
    """Return the user's profile information, API keys, and notification settings."""
    return {
        "email": user.email,
        "full_name": user.full_name or "",
        "avatar_url": user.avatar_url or "",
        "oauth_provider": user.oauth_provider,
        "bio": "",  # TODO: add bio column to users table
        "telegram_alerts": True,
        "push_notifications": False,
        # API Keys Status
        "has_binance_key": bool(user.exchange_api_key),
        "binance_api_key_last4": _safe_last4(user.exchange_api_key),
        "has_mt5_key": bool(user.meta_account_id),
        "mt_login": user.mt_login,
        "mt_server": user.mt_server,
        "mt_status": user.mt_status,
        "ea_token_active": bool(user.ea_token)
    }

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
def delete_mt5_key(user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Revoke MT5 Connection."""
    user.mt_login = None
    user.mt_password_enc = None
    user.mt_server = None
    user.mt_broker = None
    user.meta_account_id = None
    user.mt_status = "disconnected"
    db.commit()
    return {"message": "MT5 connection revoked"}

@router.get("/")
def get_users():
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
    from app.services.metaapi_service import provision_account, deploy_account, poll_until_connected

    # 1. Save encrypted broker credentials
    user.mt_login = req.mt_login
    user.mt_password_enc = encrypt_password(req.mt_password)
    user.mt_server = req.mt_server
    user.mt_broker = req.mt_broker
    user.mt_status = "connecting"
    db.commit()

    # 2. Provision cloud account
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

    # 3. Trigger deploy
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
def get_mt_status(user=Depends(get_current_user)):
    """Returns the current MetaApi connection status for the authenticated user."""
    return {
        "mt_status": getattr(user, "mt_status", "disconnected"),
        "mt_broker": getattr(user, "mt_broker", None),
        "mt_server": getattr(user, "mt_server", None),
        "mt_login": getattr(user, "mt_login", None),
        "meta_account_id": getattr(user, "meta_account_id", None),
    }
