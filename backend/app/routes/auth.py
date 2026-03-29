from fastapi import APIRouter, Depends, HTTPException, Response, Cookie, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel
from uuid import uuid4
import os
import httpx
import jwt as pyjwt
import logging
from datetime import datetime, timezone
from urllib.parse import urlparse

from app.database.db import get_db
from app.utils.security import (
    hash_password, verify_password, create_access_token,
    create_refresh_token, decode_refresh_token, REFRESH_TOKEN_EXPIRE_MINUTES,
)
from app.models.user import User
from app.models.oauth_account import OAuthAccount, AuthProvider
from app.services.analytics import AnalyticsService
from app.services.google_auth_service import GoogleAuthService
from app.config import GOOGLE_CLIENT_ID, FRONTEND_URL

logger = logging.getLogger(__name__)

router = APIRouter()

# ─── Cookie Configuration ────────────────────────────────────────────────────

ENV = os.getenv("ENV", "development")
_is_production = ENV == "production"
_is_https = _is_production

# Cross-origin (Vercel frontend ↔ Fly.io backend) requires SameSite=None + Secure.
# Same-origin / local dev can use Lax.
_samesite: str = "none" if _is_production else "lax"

# Guard: SameSite=None MUST have Secure=True, otherwise browsers silently reject
if _samesite == "none" and not _is_https:
    raise RuntimeError(
        "Cookie misconfiguration: SameSite=None requires Secure=True (HTTPS). "
        "Set ENV=production only when deployed behind HTTPS."
    )

# Build the allowed origin set for CSRF validation.
_frontend_url = (FRONTEND_URL or "").strip()
_allowed_origins: set[str] = {
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost",
    "http://127.0.0.1",
}
if _frontend_url and _frontend_url != "*":
    for origin in _frontend_url.split(","):
        origin = origin.strip()
        if origin:
            _allowed_origins.add(origin)

COOKIE_SETTINGS = dict(
    key="refresh_token",
    httponly=True,
    secure=_is_https,
    samesite=_samesite,
    max_age=REFRESH_TOKEN_EXPIRE_MINUTES * 60,
    path="/auth",  # Only sent to /auth/* endpoints — minimal exposure
)


def _set_refresh_cookie(response: Response, user_id: str):
    """Set the HttpOnly refresh token cookie on a response."""
    response.set_cookie(value=create_refresh_token(user_id), **COOKIE_SETTINGS)


def _clear_refresh_cookie(response: Response):
    """Delete the refresh token cookie."""
    response.delete_cookie(
        key="refresh_token",
        httponly=True,
        secure=_is_https,
        samesite=_samesite,
        path="/auth",
    )


# ─── Schemas ──────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: str
    password: str

class LoginRequest(BaseModel):
    email: str
    password: str

class OAuthRequest(BaseModel):
    token: str  # Google: credential from One Tap


# ─── Email / Password ────────────────────────────────────────────────────────

@router.post("/register")
def register(data: RegisterRequest, db: Session = Depends(get_db)):
    email = data.email.lower()
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        id=str(uuid4()),
        email=email,
        password_hash=hash_password(data.password)
    )
    db.add(user)
    try:
        AnalyticsService.record_new_user(db)
    except Exception as e:
        logger.warning(f"Failed to record analytics for new user: {e}")
    db.commit()
    return {"message": "user created"}


@router.post("/login")
def login(data: LoginRequest, response: Response, db: Session = Depends(get_db)):
    email = data.email.lower()
    user = db.query(User).filter(User.email == email).first()

    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not user.password_hash:
        raise HTTPException(
            status_code=401,
            detail="This account uses social login. Please sign in with Google."
        )

    if not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    user.last_login = datetime.now(timezone.utc)
    db.commit()
    token = create_access_token(user.id)
    _set_refresh_cookie(response, user.id)
    return {"access_token": token, "token_type": "bearer"}


# ─── Google OAuth ─────────────────────────────────────────────────────────────

@router.post("/google")
async def google_login(data: OAuthRequest, response: Response, db: Session = Depends(get_db)):
    """
    Verifies a Google ID token, creates or links the user, and returns a JWT.
    """
    # 1. Verify token securely using google-auth library
    payload = GoogleAuthService.verify_token(data.token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or unverified Google token")

    google_sub = payload.get("sub")
    email = payload.get("email", "").lower()
    name = payload.get("name")
    picture = payload.get("picture")

    if not email or not google_sub:
        raise HTTPException(status_code=401, detail="Incomplete Google profile")

    # 2. Primary Identity Lookup: Check OAuthAccount table first
    oauth_acc = db.query(OAuthAccount).filter(
        OAuthAccount.provider == AuthProvider.GOOGLE,
        OAuthAccount.provider_sub == google_sub
    ).first()

    user = None
    if oauth_acc:
        user = oauth_acc.user
        logger.info(f"OAuth Account found: user_id={user.id if user else 'NONE'}")
        # Update metadata if changed
        oauth_acc.provider_name = name or oauth_acc.provider_name
        oauth_acc.provider_avatar = picture or oauth_acc.provider_avatar
        oauth_acc.last_used_at = datetime.now(timezone.utc)
    else:
        # 3. Secondary Lookup: Fallback to Email Identity (Account Linking)
        logger.info(f"No OAuth account for sub {google_sub}. Checking email {email}")
        user = db.query(User).filter(User.email == email).first()

        if user:
            logger.info(f"Existing user found by email: user_id={user.id}")
            # Found existing user by email, link this Google account
            new_oauth = OAuthAccount(
                id=str(uuid4()),
                user_id=user.id,
                provider=AuthProvider.GOOGLE,
                provider_sub=google_sub,
                provider_email=email,
                provider_name=name,
                provider_avatar=picture
            )
            db.add(new_oauth)
            # Mark email as verified if Google says so (we already checked in service)
            user.email_verified = True
        else:
            # 4. Identity Creation: New User and OAuth record
            logger.info(f"No user found for email {email}. Creating new user.")
            user = User(
                id=str(uuid4()),
                email=email,
                email_verified=True
            )
            db.add(user)
            db.flush() # Get user.id
            logger.info(f"New user created: user_id={user.id}")

            new_oauth = OAuthAccount(
                id=str(uuid4()),
                user_id=user.id,
                provider=AuthProvider.GOOGLE,
                provider_sub=google_sub,
                provider_email=email,
                provider_name=name,
                provider_avatar=picture
            )
            db.add(new_oauth)

            try:
                AnalyticsService.record_new_user(db)
            except Exception as e:
                logger.warning(f"Failed to record analytics for new user: {e}")

    user.last_login = datetime.now(timezone.utc)
    db.commit()

    # Issue standardized JWT
    token = create_access_token(user.id)
    _set_refresh_cookie(response, user.id)
    logger.info(f"Successfully logged in: {email} (user_id={user.id})")
    return {"access_token": token, "token_type": "bearer"}


# ─── CSRF Protection ─────────────────────────────────────────────────────────

def _verify_csrf(request: Request):
    """Block cross-origin cookie-bearing POSTs (CSRF).

    Checks the Origin header (set by browsers on all non-GET requests).
    Falls back to Referer when Origin is absent (some privacy proxies strip it).
    """
    origin = request.headers.get("origin")
    if not origin:
        # Some browsers/proxies omit Origin; check Referer as fallback
        referer = request.headers.get("referer")
        if referer:
            parsed = urlparse(referer)
            origin = f"{parsed.scheme}://{parsed.netloc}"

    if not origin:
        # No origin info at all — allow in dev, block in prod
        if _is_production:
            raise HTTPException(status_code=403, detail="Missing origin header")
        return

    if origin not in _allowed_origins:
        logger.warning(f"CSRF blocked: origin={origin}")
        raise HTTPException(status_code=403, detail="Invalid origin")


# ─── Token Refresh ────────────────────────────────────────────────────────────

@router.post("/refresh")
def refresh_token(
    request: Request,
    response: Response,
    refresh_token: str | None = Cookie(None),
    db: Session = Depends(get_db),
):
    """Exchange a valid refresh-token cookie for a new access token."""
    _verify_csrf(request)

    if not refresh_token:
        raise HTTPException(status_code=401, detail="Missing refresh token")

    user_id = decode_refresh_token(refresh_token)
    if not user_id:
        _clear_refresh_cookie(response)
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        _clear_refresh_cookie(response)
        raise HTTPException(status_code=401, detail="User not found")

    # Rotate: issue fresh refresh token on each use (limits replay window)
    _set_refresh_cookie(response, user.id)
    return {"access_token": create_access_token(user.id), "token_type": "bearer"}


# ─── Logout ──────────────────────────────────────────────────────────────────

@router.post("/logout")
def logout(request: Request, response: Response):
    """Clear the refresh token cookie."""
    _verify_csrf(request)
    _clear_refresh_cookie(response)
    return {"message": "logged out"}
