from sqlalchemy import Column, String, Float, Integer, ForeignKey
from sqlalchemy.orm import relationship
import uuid

from app.database.db import Base

class Plan(Base):
    __tablename__ = "plans"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, unique=True, nullable=False, index=True) # e.g., "Starter", "Pro", "Elite"
    max_strategies = Column(Integer, default=1)
    price_usd = Column(Float, default=0.0)

    # Relationships
    allowed_strategies = relationship("PlanStrategy", back_populates="plan", cascade="all, delete-orphan")
    users = relationship("User", back_populates="plan")


class PlanStrategy(Base):
    __tablename__ = "plan_strategies"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    plan_id = Column(String, ForeignKey("plans.id", ondelete="CASCADE"), nullable=False, index=True)
    bot_id = Column(String, ForeignKey("bots.id", ondelete="CASCADE"), nullable=False, index=True)

    # Relationships
    plan = relationship("Plan", back_populates="allowed_strategies")
    bot = relationship("Bot")
