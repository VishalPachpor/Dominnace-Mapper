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
    
    # MT5 / EA Bridge
    ea_token = Column(String, unique=True, nullable=True)
    ea_last_seen = Column(DateTime, nullable=True)
    mt5_balance = Column(Float, default=0.0)
    mt5_equity = Column(Float, default=0.0)

    is_active = Column(Boolean, default=True)

