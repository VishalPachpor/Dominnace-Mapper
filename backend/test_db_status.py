from app.database.db import SessionLocal
from app.models.user import User

db = SessionLocal()
users = db.query(User).all()
for u in users:
    print(f"User {u.id}: MT Status: {u.mt_status}, Login: {u.mt_login}")
db.close()
