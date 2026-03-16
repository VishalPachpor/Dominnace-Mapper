from sqlalchemy import Column, String, Float, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.database.db import Base

class TradeState(Base):
    """
    Tracks the lifecycle of DOM trades (and others) for advanced logic like
    Breakeven (BE) and Reversals.
    """
    __tablename__ = "trade_states"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    symbol = Column(String, nullable=False, index=True)
    position_id = Column(String, nullable=True, index=True) # ID from positions table / MetaApi
    bot_slug = Column(String, nullable=False, index=True) # E.g., dm-bull
    
    # Position details
    entry_price = Column(Float, nullable=False)
    sl_price = Column(Float, nullable=False)
    tp_price = Column(Float, nullable=False)
    be_trigger = Column(Float, nullable=False)
    
    side = Column(String, nullable=False) # 'buy' or 'sell'
    
    # State flags
    status = Column(String, default="OPEN", index=True) # OPEN, BREAKEVEN, REVERSED, CLOSED
    reversal_used = Column(Boolean, default=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", backref="trade_states")
