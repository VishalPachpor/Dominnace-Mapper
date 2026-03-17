from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database.db import get_db
from app.models.user import User
from app.models.position import Position
from app.utils.security import get_current_user

router = APIRouter()

def require_admin(user: User = Depends(get_current_user)):
    if not user.is_admin:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Admin access required")
    return user

@router.get("/")
def list_trades(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """Global trade feed."""
    trades = db.query(Position, User.email)\
        .join(User, Position.user_id == User.id)\
        .order_by(Position.created_at.desc())\
        .limit(100).all()
        
    results = []
    for pos, email in trades:
        results.append({
            "id": pos.id,
            "user": email,
            "symbol": pos.symbol,
            "side": pos.side,
            "entry_price": pos.entry,
            "exit_price": pos.exit_price,
            "pnl": pos.pnl,
            "status": pos.status,
            "created_at": pos.created_at
        })
    return results
