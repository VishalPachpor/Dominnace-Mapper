import sys
import os

sys.path.insert(0, os.path.abspath("/app"))
from app.database.db import SessionLocal
from sqlalchemy import text

db = SessionLocal()
try:
    print("Adding missing columns...")
    db.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'active'"))
    db.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP"))
    db.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login TIMESTAMP WITHOUT TIME ZONE"))
    db.commit()
    print("Columns added successfully.")
except Exception as e:
    db.rollback()
    print(f"Failed: {e}")
finally:
    db.close()
