from sqlalchemy import Column, String, Boolean, DateTime, Float
from app.database.db import Base
from uuid import uuid4

class User(Base):

    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    
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
