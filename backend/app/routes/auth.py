from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from uuid import uuid4
import httpx
import jwt as pyjwt
import logging
from datetime import datetime

from app.database.db import get_db
from app.utils.security import hash_password, verify_password, create_access_token
from app.models.user import User
from app.models.oauth_account import OAuthAccount, AuthProvider
from app.services.analytics import AnalyticsService
from app.services.google_auth_service import GoogleAuthService
from app.config import GOOGLE_CLIENT_ID

logger = logging.getLogger(__name__)

router = APIRouter()


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
    except:
        pass
    db.commit()
    return {"message": "user created"}


@router.post("/login")
def login(data: LoginRequest, db: Session = Depends(get_db)):
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

    user.last_login = datetime.utcnow()
    db.commit()
    token = create_access_token(user.id)
    return {"access_token": token, "token_type": "bearer"}


# ─── Google OAuth ─────────────────────────────────────────────────────────────

@router.post("/google")
async def google_login(data: OAuthRequest, db: Session = Depends(get_db)):
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
        oauth_acc.last_used_at = datetime.utcnow()
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
            except:
                pass

    user.last_login = datetime.utcnow()
    db.commit()

    # Issue standardized JWT
    token = create_access_token(user.id)
    logger.info(f"Successfully logged in: {email} (user_id={user.id})")
    return {"access_token": token, "token_type": "bearer"}
