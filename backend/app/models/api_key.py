from sqlalchemy import Column, String
from app.database.db import Base

class APIKey(Base):

    __tablename__ = "api_keys"

    id = Column(String, primary_key=True)
    user_id = Column(String)
    exchange = Column(String)
    api_key_encrypted = Column(String)
    api_secret_encrypted = Column(String)
