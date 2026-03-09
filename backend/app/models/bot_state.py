from sqlalchemy import Column, String, Boolean, DateTime
from app.database.db import Base
from datetime import datetime, timezone

class BotState(Base):

    __tablename__ = "bot_state"

    user_id = Column(String, primary_key=True)
    symbol = Column(String, primary_key=True)
    state = Column(String)  # IDLE, OPEN_TRADE, REVERSAL, STANDBY
    
    reversal_used = Column(Boolean, default=False)
    standby = Column(Boolean, default=False)
    
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
