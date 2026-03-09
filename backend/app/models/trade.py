from sqlalchemy import Column, String, Integer, Float, DateTime
from app.database.db import Base
from datetime import datetime, timezone
from uuid import uuid4

class Trade(Base):

    __tablename__ = "trades"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(String, nullable=True)
    symbol = Column(String)
    side = Column(String)

    entry = Column(Float)
    exit = Column(Float)
    pnl = Column(Float)

    result = Column(String)  # WIN, LOSS, BREAKEVEN
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
