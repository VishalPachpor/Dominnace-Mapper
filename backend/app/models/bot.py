from sqlalchemy import Column, String, Float, Boolean, ForeignKey, DateTime, Integer, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.database.db import Base

class Bot(Base):
    __tablename__ = "bots"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    slug = Column(String, unique=True, nullable=False, index=True)
    description = Column(String, nullable=True)
    risk_level = Column(String, default="Medium") # e.g. Low, Medium, High
    timeframe = Column(String, default="15m")
    supported_symbols = Column(String, default="All") # e.g. "BTC/USDT, ETH/USDT"
    symbol = Column(String, nullable=True)
    max_lot_size = Column(Float, default=0.01)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user_subscriptions = relationship("UserBot", back_populates="bot", cascade="all, delete-orphan")


class UserBot(Base):
    __tablename__ = "user_bots"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    bot_id = Column(String, ForeignKey("bots.id", ondelete="CASCADE"), nullable=False, index=True)
    is_enabled = Column(Boolean, default=True)
    custom_lot_size = Column(Float, nullable=True) # Optional override
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('user_id', 'bot_id', name='uix_user_bot'),
    )

    # Relationships
    user = relationship("User", backref="bot_subscriptions")
    bot = relationship("Bot", back_populates="user_subscriptions")
