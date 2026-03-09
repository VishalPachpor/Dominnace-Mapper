from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime
from app.database.db import Base
from datetime import datetime, timezone
from uuid import uuid4

class Position(Base):

    __tablename__ = "positions"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(String, nullable=True)
    symbol = Column(String)
    side = Column(String)

    entry = Column(Float)
    sl = Column(Float)
    tp = Column(Float)

    be_trigger = Column(Float)

    is_reversal = Column(Boolean, default=False)
    be_moved = Column(Boolean, default=False)

    status = Column(String)  # OPEN, CLOSED, STOPPED, TP_HIT, pending_ea, executed, failed
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    # EA Bridge Execution tracking
    ea_picked_at = Column(DateTime, nullable=True)
    executed_price = Column(Float, nullable=True)
