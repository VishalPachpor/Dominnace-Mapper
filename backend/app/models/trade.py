from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database.db import Base
from datetime import datetime, timezone
from uuid import uuid4

class Trade(Base):

    __tablename__ = "trades"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    signal_id = Column(String, ForeignKey("signals.id"), nullable=True, index=True)
    bot_id = Column(String, ForeignKey("bots.id", ondelete="SET NULL"), nullable=True, index=True)
    symbol = Column(String, index=True)
    side = Column(String) # BUY / SELL

    entry = Column(Float)
    exit = Column(Float, nullable=True)
    pnl = Column(Float, default=0.0)
    lot_size = Column(Float, nullable=True)

    execution_time = Column(DateTime, nullable=True, index=True)
    close_time = Column(DateTime, nullable=True)
    execution_latency_ms = Column(Integer, nullable=True)

    status = Column(String, default="OPEN", index=True)  # OPEN, CLOSING, CLOSED, EXECUTION_FAILED
    result = Column(String, nullable=True)  # WIN, LOSS, BREAKEVEN
    reject_reason = Column(String, nullable=True)  # Detailed reason for EXECUTION_FAILED
    metaapi_trade_id = Column(String, nullable=True)
    last_synced_at = Column(DateTime, nullable=True, index=True)
    retry_count = Column(Integer, default=0)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    signal = relationship("Signal", backref="trades")
