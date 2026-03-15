import os
os.environ["DATABASE_URL"] = "postgresql://lingering_moon_9343:44Alzy6eqsyf4ND@localhost:54320/lingering_moon_9343?sslmode=disable"

from app.database.db import SessionLocal
from app.models.user import User
from app.utils.security import hash_password
from uuid import uuid4

try:
    db = SessionLocal()
    user = User(
        id=str(uuid4()),
        email="test_catch@test.com",
        password_hash=hash_password("password")
    )
    db.add(user)
    db.commit()
    print("SUCCESSFUL REGISTRATION IN DB!")
except Exception as e:
    print("REGISTRATION FAILED WITH ERROR:", str(e))
    import traceback
    traceback.print_exc()
