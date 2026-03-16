from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database.db import get_db
from app.models.user import User
from app.models.strategy_stats import StrategyStats
from app.utils.security import get_current_user

router = APIRouter()

def require_admin(user: User = Depends(get_current_user)):
    if not user.is_admin:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Admin access required")
    return user

@router.get("/")
def get_strategy_stats(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """Get aggregated performance stats per strategy."""
    stats = db.query(StrategyStats).all()
    return stats
