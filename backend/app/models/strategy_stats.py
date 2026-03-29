from sqlalchemy import Column, String, Integer, Float, DateTime
from datetime import datetime, timezone
from app.database.db import Base

class StrategyStats(Base):
    __tablename__ = "strategy_stats"

    bot_slug = Column(String, primary_key=True) # References Bot.slug
    total_trades = Column(Integer, default=0)
    total_pnl = Column(Float, default=0.0)
    wins = Column(Integer, default=0)
    losses = Column(Integer, default=0)
    last_updated = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
