import sys
import os
import enum
from uuid import uuid4
from datetime import datetime

# Add the backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database.db import SessionLocal
from app.models.user import User
from app.models.oauth_account import OAuthAccount, AuthProvider

def backfill_oauth():
    db = SessionLocal()
    try:
        # Find users with existing OAuth data
        users = db.query(User).filter(User.oauth_provider.isnot(None)).all()
        print(f"Found {len(users)} users with existing OAuth data.")

        for user in users:
            # Check if an OAuthAccount already exists for this provider/sub
            existing_oauth = db.query(OAuthAccount).filter(
                OAuthAccount.provider == user.oauth_provider,
                OAuthAccount.provider_sub == user.oauth_sub
            ).first()

            if not existing_oauth:
                print(f"Backfilling OAuth for user: {user.email} (Provider: {user.oauth_provider})")
                
                # try to parse provider string to enum
                provider_enum = None
                try:
                    provider_enum = AuthProvider(user.oauth_provider)
                except ValueError:
                    print(f"Unknown provider: {user.oauth_provider}. Skipping.")
                    continue

                new_oauth = OAuthAccount(
                    id=str(uuid4()),
                    user_id=user.id,
                    provider=provider_enum,
                    provider_sub=user.oauth_sub,
                    provider_email=user.email,
                    provider_name=user.full_name,
                    provider_avatar=user.avatar_url,
                    created_at=user.created_at or datetime.utcnow(),
                    last_used_at=user.last_login or datetime.utcnow()
                )
                db.add(new_oauth)
            else:
                print(f"OAuth record already exists for user: {user.email}")

        db.commit()
        print("Backfill completed successfully.")
    except Exception as e:
        db.rollback()
        print(f"Error during backfill: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    backfill_oauth()
