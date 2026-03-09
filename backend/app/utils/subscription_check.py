from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from app.models.subscription import Subscription
from app.models.user import User
from app.database.db import get_db
from app.utils.security import get_current_user
from datetime import datetime, timezone

def check_subscription_active(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """FastAPI dependency that verifies the current user has an active subscription."""
    subscription = db.query(Subscription).filter(Subscription.user_id == user.id).first()
    
    if not subscription:
        raise HTTPException(status_code=403, detail="No active subscription found. Please subscribe to use the bot.")
    
    if subscription.status != "active":
        # Allow grace period of 3 days
        if subscription.current_period_end:
            grace_period_end = subscription.current_period_end.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            if (now - grace_period_end).days > 3:
                raise HTTPException(status_code=403, detail="Subscription expired. Please update your billing information.")
    
    return subscription
