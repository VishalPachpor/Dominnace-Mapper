from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from uuid import uuid4
import httpx
import jwt as pyjwt
import logging

from app.database.db import get_db
from app.utils.security import hash_password, verify_password, create_access_token
from app.models.user import User
from app.config import GOOGLE_CLIENT_ID, APPLE_CLIENT_ID

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
    token: str  # Google: credential from One Tap / Apple: id_token


# ─── Email / Password ────────────────────────────────────────────────────────

@router.post("/register")
def register(data: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == data.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        id=str(uuid4()),
        email=data.email,
        password_hash=hash_password(data.password)
    )
    db.add(user)
    db.commit()
    return {"message": "user created"}


@router.post("/login")
def login(data: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()

    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not user.password_hash:
        raise HTTPException(
            status_code=401,
            detail="This account uses social login. Please sign in with Google or Apple."
        )

    if not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token(user.id)
    return {"access_token": token, "token_type": "bearer"}


# ─── Google OAuth ─────────────────────────────────────────────────────────────

@router.post("/google")
async def google_login(data: OAuthRequest, db: Session = Depends(get_db)):
    """
    Verifies a Google ID token (from Google One Tap or Sign-In),
    creates or links the user, and returns a JWT.
    """
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=500, detail="Google OAuth not configured")

    # Verify the token with Google's public keys
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"https://oauth2.googleapis.com/tokeninfo?id_token={data.token}"
            )
            if resp.status_code != 200:
                raise HTTPException(status_code=401, detail="Invalid Google token")
            payload = resp.json()
    except httpx.HTTPError:
        raise HTTPException(status_code=401, detail="Failed to verify Google token")

    # Validate audience matches our client ID
    if payload.get("aud") != GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=401, detail="Token audience mismatch")

    if payload.get("email_verified") not in ("true", True):
        raise HTTPException(status_code=401, detail="Google email not verified")

    google_sub = payload.get("sub")
    email = payload.get("email")
    name = payload.get("name")
    picture = payload.get("picture")

    if not email or not google_sub:
        raise HTTPException(status_code=401, detail="Incomplete Google profile")

    # Find or create user
    user = db.query(User).filter(User.oauth_sub == google_sub).first()

    if not user:
        # Check if email already exists (email/password user linking to Google)
        user = db.query(User).filter(User.email == email).first()
        if user:
            # Link Google to existing account
            user.oauth_provider = "google"
            user.oauth_sub = google_sub
            user.full_name = user.full_name or name
            user.avatar_url = user.avatar_url or picture
        else:
            # Brand new user
            user = User(
                id=str(uuid4()),
                email=email,
                oauth_provider="google",
                oauth_sub=google_sub,
                full_name=name,
                avatar_url=picture,
            )
            db.add(user)

    db.commit()
    token = create_access_token(user.id)
    logger.info(f"Google OAuth login: {email} (user_id={user.id})")
    return {"access_token": token, "token_type": "bearer"}


# ─── Apple OAuth ──────────────────────────────────────────────────────────────

# Apple public keys cache
_apple_keys_cache: dict | None = None

async def _get_apple_public_keys() -> dict:
    global _apple_keys_cache
    if _apple_keys_cache:
        return _apple_keys_cache
    async with httpx.AsyncClient() as client:
        resp = await client.get("https://appleid.apple.com/auth/keys")
        resp.raise_for_status()
        _apple_keys_cache = resp.json()
        return _apple_keys_cache


@router.post("/apple")
async def apple_login(data: OAuthRequest, db: Session = Depends(get_db)):
    """
    Verifies an Apple ID token, creates or links the user, and returns a JWT.
    Apple sends: id_token (JWT signed with Apple's RSA keys).
    """
    if not APPLE_CLIENT_ID:
        raise HTTPException(status_code=500, detail="Apple OAuth not configured")

    try:
        # Decode header to find the key ID
        unverified_header = pyjwt.get_unverified_header(data.token)
        kid = unverified_header.get("kid")

        # Fetch Apple's public keys
        apple_keys = await _get_apple_public_keys()
        matching_key = None
        for key in apple_keys.get("keys", []):
            if key["kid"] == kid:
                matching_key = key
                break

        if not matching_key:
            raise HTTPException(status_code=401, detail="Apple key not found")

        # Build RSA public key and verify
        from jwt.algorithms import RSAAlgorithm
        public_key = RSAAlgorithm.from_jwk(matching_key)

        payload = pyjwt.decode(
            data.token,
            public_key,
            algorithms=["RS256"],
            audience=APPLE_CLIENT_ID,
            issuer="https://appleid.apple.com",
        )
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Apple token expired")
    except pyjwt.InvalidTokenError as e:
        logger.error(f"Apple token validation failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid Apple token")

    apple_sub = payload.get("sub")
    email = payload.get("email")

    if not apple_sub:
        raise HTTPException(status_code=401, detail="Incomplete Apple profile")

    # Find or create user
    user = db.query(User).filter(User.oauth_sub == apple_sub).first()

    if not user:
        if email:
            user = db.query(User).filter(User.email == email).first()

        if user:
            user.oauth_provider = "apple"
            user.oauth_sub = apple_sub
        else:
            # Apple may not provide email on subsequent logins
            user = User(
                id=str(uuid4()),
                email=email or f"apple_{apple_sub[:12]}@private.relay",
                oauth_provider="apple",
                oauth_sub=apple_sub,
            )
            db.add(user)

    db.commit()
    token = create_access_token(user.id)
    logger.info(f"Apple OAuth login: {email or apple_sub} (user_id={user.id})")
    return {"access_token": token, "token_type": "bearer"}
