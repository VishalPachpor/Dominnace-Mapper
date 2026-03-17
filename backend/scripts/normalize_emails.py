from app.database.db import SessionLocal
from app.models.user import User
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def normalize_emails():
    db = SessionLocal()
    try:
        users = db.query(User).all()
        for u in users:
            old_email = u.email
            new_email = u.email.lower()
            if old_email != new_email:
                u.email = new_email
                logger.info(f"Normalized: {old_email} -> {new_email}")
        db.commit()
    except Exception as e:
        logger.error(f"Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    normalize_emails()
