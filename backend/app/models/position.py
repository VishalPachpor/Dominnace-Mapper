from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, ForeignKey
from app.database.db import Base
from datetime import datetime, timezone
from uuid import uuid4

class Position(Base):

    __tablename__ = "positions"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    bot_id = Column(String, nullable=True)
    symbol = Column(String)
    side = Column(String)

    entry = Column(Float)
    sl = Column(Float)
    tp = Column(Float)

    be_trigger = Column(Float)

    is_reversal = Column(Boolean, default=False)
    be_moved = Column(Boolean, default=False)

    status = Column(String)  # OPEN, CLOSED, STOPPED, TP_HIT, pending_ea, executed, failed
    
    # Live State / Tracking
    lot_size = Column(Float, nullable=True)
    current_price = Column(Float, nullable=True)
    unrealized_pnl = Column(Float, default=0.0)
    metaapi_position_id = Column(String, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    opened_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=True, onupdate=lambda: datetime.now(timezone.utc))
    
    # EA Bridge Execution tracking
    ea_picked_at = Column(DateTime, nullable=True)
    executed_price = Column(Float, nullable=True)

    # Added for Phase 2 scaling / Reporting fixes
    exit_price = Column(Float, nullable=True)
    pnl = Column(Float, nullable=True)
    closed_at = Column(DateTime, nullable=True)
