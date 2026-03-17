from sqlalchemy import Column, String, DateTime, JSON
from app.database.db import Base
from datetime import datetime, timezone
from uuid import uuid4


class SignalFailure(Base):
    """
    Records every signal that was dropped before reaching the execution engine.
    This ensures ZERO silent drops — every signal is either executed or explained.
    """
    __tablename__ = "signal_failures"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    reason = Column(String, nullable=False)       # BOT_NOT_FOUND, IDEMPOTENCY, NO_SUBSCRIBERS, KILL_SWITCH, etc.
    incoming_slug = Column(String, nullable=True)  # What was sent from TradingView
    symbol = Column(String, nullable=True)
    direction = Column(String, nullable=True)      # BUY / SELL
    raw_payload = Column(JSON, nullable=True)      # Full TradingView payload for debugging
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
