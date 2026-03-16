from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database.db import get_db
from app.models.user import User
from app.models.plan import Plan
from app.utils.security import get_current_user

router = APIRouter()

def require_admin(user: User = Depends(get_current_user)):
    if not user.is_admin:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Admin access required")
    return user

@router.get("/")
def get_plans_overview(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """Get user distribution and revenue estimates per plan."""
    plans = db.query(Plan).all()
    results = []
    for p in plans:
        user_count = db.query(User).filter(User.plan_id == p.id).count()
        results.append({
            "id": p.id,
            "name": p.name,
            "price": p.price_usd,
            "users": user_count,
            "monthly_revenue": round(user_count * p.price_usd, 2)
        })
    return results
