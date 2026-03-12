from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.database.db import get_db
from app.utils.security import get_current_user
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


class AddApiKeyRequest(BaseModel):
    api_key: str
    secret_key: str

@router.post("/add-api-key")
def save_api_keys(data: AddApiKeyRequest, user=Depends(get_current_user), db: Session = Depends(get_db)):
    user.exchange_api_key = data.api_key
    user.exchange_secret_key = data.secret_key
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
