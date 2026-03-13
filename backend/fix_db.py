from app.database.db import SessionLocal
from app.models.user import User

db = SessionLocal()
u = db.query(User).filter(User.mt_login == "279223").first()
if u:
    print(f"Old meta_account_id: {u.meta_account_id}")
    u.meta_account_id = "f388ba93-dc08-42fa-9384-f111a1a75af6"
    u.mt_status = "connected"
    db.commit()
    print("Updated to f388ba93-dc08-42fa-9384-f111a1a75af6 and status to connected!")
db.close()
