from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.utils.security import get_current_user
from app.models.position import Position
from app.database.db import get_db

router = APIRouter()

@router.get("")
def get_positions(user=Depends(get_current_user), db: Session = Depends(get_db)):
    positions = db.query(Position).filter(
        Position.user_id == user.id,
        Position.status == "OPEN"
    ).all()
    
    return positions
