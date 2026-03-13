import asyncio
import os
import sys

# Add backend to path so imports work
sys.path.append("/Users/vishalpatil/Dominance mapper/backend")

from app.services.metaapi_service import poll_until_connected
from app.database.db import SessionLocal
from app.models.user import User

async def main():
    db = SessionLocal()
    # Find the user we just checked
    user = db.query(User).filter(User.mt_login == "279223").first()
    if not user:
        print("User not found")
        return
        
    print(f"Testing poll for user {user.id} and account {user.meta_account_id}")
    db.close()
    
    # Run the polling function manually with a short max_wait to see exactly what logs or crashes
    try:
        await poll_until_connected(str(user.id), str(user.meta_account_id), None, max_wait=20)
    except Exception as e:
        print(f"Poll crashed: {e}")

asyncio.run(main())
