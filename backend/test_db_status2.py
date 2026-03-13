from app.database.db import SessionLocal
from app.models.user import User

db = SessionLocal()
u = db.query(User).filter(User.mt_login == "279223").first()
if u:
    print(f"User {u.id}: MT Status: {u.mt_status}, Login: {u.mt_login}, MetaAccountId: {u.meta_account_id}")
db.close()
