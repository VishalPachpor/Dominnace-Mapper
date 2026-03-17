import sys
import os

sys.path.insert(0, os.path.abspath("/app"))
from app.database.db import SessionLocal
from sqlalchemy import text

db = SessionLocal()
res = db.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='users'"))
print("\n--- COLUMNS IN USERS TABLE ---")
print([r[0] for r in res.fetchall()])
print("------------------------------\n")
db.close()
