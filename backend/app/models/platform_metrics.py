from sqlalchemy import Column, Integer, Float, Date
from app.database.db import Base

class PlatformMetrics(Base):
    __tablename__ = "platform_metrics"

    date = Column(Date, primary_key=True)
    signals = Column(Integer, default=0)
    trades = Column(Integer, default=0)
    new_users = Column(Integer, default=0)
    revenue = Column(Float, default=0.0)
