from app.database.db import engine, Base
from app.models.user import User
from app.models.bot import Bot, UserBot
from app.models.plan import Plan, PlanStrategy
from app.models.trade_state import TradeState

try:
    print("Creating tables...")
    Base.metadata.create_all(bind=engine)
    print("Done.")
except Exception as e:
    import traceback
    traceback.print_exc()
