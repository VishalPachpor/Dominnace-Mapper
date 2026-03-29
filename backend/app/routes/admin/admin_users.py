from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database.db import get_db
from app.models.user import User
from app.models.position import Position
from app.models.bot import Bot
from app.utils.security import get_current_user

router = APIRouter()

def require_admin(user: User = Depends(get_current_user)):
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user

@router.get("/")
def list_users(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """List all users with basic stats (single query with LEFT JOIN)."""
    from sqlalchemy.orm import joinedload

    # Single query: all users + aggregated trade stats via subquery
    trade_stats_subq = db.query(
        Position.user_id,
        func.count(Position.id).label("count"),
        func.coalesce(func.sum(Position.pnl), 0).label("pnl")
    ).filter(Position.status == "closed").group_by(Position.user_id).subquery()

    rows = db.query(User, trade_stats_subq.c.count, trade_stats_subq.c.pnl).outerjoin(
        trade_stats_subq, User.id == trade_stats_subq.c.user_id
    ).options(joinedload(User.plan)).all()

    results = []
    for u, trade_count, trade_pnl in rows:
        results.append({
            "id": u.id,
            "email": u.email,
            "plan": u.plan.name if u.plan else "None",
            "mt_status": u.mt_status,
            "status": u.status,
            "total_trades": trade_count or 0,
            "total_pnl": round(float(trade_pnl or 0), 2),
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "last_login": u.last_login.isoformat() if u.last_login else None
        })

    return results

@router.get("/{user_id}")
def get_user_detail(user_id: str, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """Detailed view of a single user."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    trades = db.query(Position).filter(Position.user_id == user_id).order_by(Position.created_at.desc()).limit(50).all()
    
    return {
        "profile": {
            "email": user.email,
            "fullName": user.full_name,
            "status": user.status,
            "plan": user.plan.name if user.plan else "None",
            "mt_status": user.mt_status,
            "metaAccountId": user.meta_account_id,
            "createdAt": user.created_at,
            "lastLogin": user.last_login
        },
        "recent_trades": trades
    }
