from sqlalchemy import Column, Integer, String, Float
from app.database.db import Base

class Signal(Base):

    __tablename__ = "signals"

    id = Column(Integer, primary_key=True)
    symbol = Column(String)
    action = Column(String)
    price = Column(Float)
