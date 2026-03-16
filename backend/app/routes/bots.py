from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
import datetime

from app.database.db import get_db
from app.models.user import User
from app.models.bot import Bot, UserBot
from app.models.plan import Plan, PlanStrategy
from app.models.subscription import Subscription
from app.utils.security import get_current_user

router = APIRouter()

# Pydantic Schemas
class BotResponse(BaseModel):
    id: str
    name: str
    slug: str
    description: Optional[str]
    risk_level: Optional[str]
    timeframe: Optional[str]
    supported_symbols: Optional[str]
    symbol: Optional[str]
    max_lot_size: float
    is_active: bool
    is_enabled: Optional[bool] = False
    
    class Config:
        from_attributes = True

class UserBotResponse(BaseModel):
    id: str
    bot_id: str
    is_enabled: bool
    custom_lot_size: Optional[float]
    created_at: datetime.datetime
    
    class Config:
        from_attributes = True

class ToggleBotRequest(BaseModel):
    enabled: bool

@router.get("", response_model=List[BotResponse])
def get_all_bots(db: Session = Depends(get_db)):
    bots = db.query(Bot).filter(Bot.is_active == True).all()
    return bots

# Move /users/me/bots here or handle via APIRouter tags
# Or we can put it under /users, but it's simpler to keep it grouped logically
from app.services.bot_analytics import get_bot_leaderboard

@router.get("/public/leaderboard")
def get_public_leaderboard(db: Session = Depends(get_db)):
    """
    Publicly accessible leaderboard for marketing and landing pages.
    No authentication required.
    """
    return get_bot_leaderboard(db)

@router.get("/my-subscriptions", response_model=List[UserBotResponse])
def get_my_bots(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user_bots = db.query(UserBot).filter(UserBot.user_id == current_user.id).all()
    return user_bots

@router.get("/strategies", response_model=List[BotResponse])
def get_user_strategies(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Returns a dynamic list of strategies available based on the user's current plan.
    Includes 'is_enabled' status for each bot.
    """
    # 1. Get user's plan
    if not current_user.plan_id:
        # Fallback to Starter if no plan assigned
        starter = db.query(Plan).filter(Plan.name == "Starter").first()
        if starter:
            current_user.plan_id = starter.id
            db.commit()
    
    # 2. Get allowed bot IDs from plan_strategies
    allowed_bot_ids = db.query(PlanStrategy.bot_id).filter(PlanStrategy.plan_id == current_user.plan_id).all()
    allowed_bot_ids = [b[0] for b in allowed_bot_ids]
    
    # 3. Get the bots
    bots = db.query(Bot).filter(Bot.id.in_(allowed_bot_ids), Bot.is_active == True).all()
    
    # 4. Get user's current enabled statuses
    user_bots = db.query(UserBot).filter(UserBot.user_id == current_user.id).all()
    enabled_map = {ub.bot_id: ub.is_enabled for ub in user_bots}
    
    # 5. Build response
    result_list = []
    for bot in bots:
        res = BotResponse.from_orm(bot)
        res.is_enabled = enabled_map.get(bot.id, False)
        result_list.append(res)
        
    return result_list

@router.post("/{bot_id}/toggle", response_model=UserBotResponse)
def toggle_bot_subscription(
    bot_id: str,
    payload: ToggleBotRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    bot = db.query(Bot).filter(Bot.id == bot_id, Bot.is_active == True).first()
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found or inactive")

    # Get user's plan limits
    plan = current_user.plan
    if not plan:
        plan = db.query(Plan).filter(Plan.name == "Starter").first()
    
    max_bots = plan.max_strategies if plan else 1

    # Find existing association
    user_bot = db.query(UserBot).filter(
        UserBot.user_id == current_user.id,
        UserBot.bot_id == bot_id
    ).first()

    if payload.enabled:
        # Check limits before enabling
        active_bots_count = db.query(UserBot).filter(
            UserBot.user_id == current_user.id, 
            UserBot.is_enabled == True
        ).count()
        
        # If toggling an existing inactive bot, or inserting a new one
        if (not user_bot or not user_bot.is_enabled) and active_bots_count >= max_bots:
            raise HTTPException(
                status_code=403, 
                detail=f"Subscription limit reached. Your plan allows max {max_bots} active bot(s)."
            )

        if not user_bot:
            user_bot = UserBot(user_id=current_user.id, bot_id=bot_id, is_enabled=True)
            db.add(user_bot)
        else:
            user_bot.is_enabled = True
    else:
        # Simply disable
        if user_bot:
            user_bot.is_enabled = False
        else:
            # Trying to disable a non-existent subscription
            user_bot = UserBot(user_id=current_user.id, bot_id=bot_id, is_enabled=False)
            db.add(user_bot)

    db.commit()
    db.refresh(user_bot)
    
    return user_bot
