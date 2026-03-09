from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from app.database.db import get_db
from app.models.user import User
from app.models.position import Position
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timezone
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

class EAConfirm(BaseModel):
    trade_id: str
    status: str
    price: float

@router.get("/signals")
def get_signals(
    ea_token: str = Header(None),
    balance: float = 0.0,
    equity: float = 0.0, 
    db: Session = Depends(get_db)
):
    if not ea_token:
        # Fallback to query param for easier EA integration
        pass

    # EA requests are frequent, we need fast Auth
    user = db.query(User).filter(User.ea_token == ea_token).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid EA Token")
        
    user.ea_last_seen = datetime.now(timezone.utc)
    
    if balance > 0:
        user.mt5_balance = balance
        user.mt5_equity = equity
        
    db.commit()

    trades = db.query(Position).filter(
        Position.user_id == user.id,
        Position.status == "pending_ea"
    ).all()
    
    results = []
    for t in trades:
        # Mark as picked_up to prevent duplicate execution
        t.status = "picked_up"
        t.ea_picked_at = datetime.now(timezone.utc)
        results.append({
            "id": t.id,
            "symbol": t.symbol,
            "side": t.side,
            "lot": 0.01, # For now standard 0.01 volume
            "sl": t.sl,
            "tp": t.tp
        })
    db.commit()
    
    return results

@router.post("/confirm")
def confirm_trade(data: EAConfirm, ea_token: str = Header(None), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.ea_token == ea_token).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid EA Token")

    trade = db.query(Position).filter(Position.id == data.trade_id, Position.user_id == user.id).first()
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
        
    trade.status = data.status
    trade.executed_price = data.price
    db.commit()
    
    logger.info(f"EA confirmed trade {data.trade_id} with status {data.status} at {data.price}")
    return {"status": "success"}
