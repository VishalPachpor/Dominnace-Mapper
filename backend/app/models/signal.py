from sqlalchemy import Column, String, Float, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from app.database.db import Base
from datetime import datetime, timezone
from uuid import uuid4

class Signal(Base):
    __tablename__ = "signals"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    bot_id = Column(String, ForeignKey("bots.id"), nullable=True)

    symbol = Column(String)
    direction = Column(String)  # LONG / SHORT

    signal_time = Column(DateTime, nullable=True)
    price_at_signal = Column(Float, nullable=True)

    raw_payload = Column(JSONB, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
