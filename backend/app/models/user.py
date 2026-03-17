from sqlalchemy import Column, String, Boolean, DateTime, Float, ForeignKey
from app.database.db import Base
from sqlalchemy.orm import relationship
from uuid import uuid4
from datetime import datetime

class User(Base):

    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=True)  # Nullable for OAuth-only users
    email_verified = Column(Boolean, default=False)

    full_name = Column(String(200), nullable=True)
    avatar_url = Column(String(500), nullable=True)

    # Relationships
    oauth_accounts = relationship("OAuthAccount", back_populates="user", cascade="all, delete-orphan")
    
    # Binance / CCXT
    exchange_api_key = Column(String, nullable=True)
    exchange_secret_key = Column(String, nullable=True)
    
    # MT5 / EA Bridge (legacy)
    ea_token = Column(String, unique=True, nullable=True)
    ea_last_seen = Column(DateTime, nullable=True)
    mt5_balance = Column(Float, default=0.0)
    mt5_equity = Column(Float, default=0.0)

    # MetaApi Cloud MT5 Integration
    mt_login = Column(String(50), nullable=True)
    mt_password_enc = Column(String, nullable=True)   # Fernet-encrypted
    mt_server = Column(String(100), nullable=True)
    mt_broker = Column(String(100), nullable=True)
    meta_account_id = Column(String(100), nullable=True)
    # Status: disconnected | connecting | deploying | connected | error
    mt_status = Column(String(30), default="disconnected")

    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    trading_paused = Column(Boolean, default=False)
    
    # Tracking & Status
    status = Column(String(20), default="active") # active | suspended | banned
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    last_login = Column(DateTime, nullable=True)
    
    # Subscription Plan
    plan_id = Column(String, ForeignKey("plans.id", ondelete="SET NULL"), nullable=True, index=True)
    plan = relationship("Plan", back_populates="users")
