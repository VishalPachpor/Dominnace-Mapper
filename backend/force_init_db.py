import os

os.environ["DATABASE_URL"] = "postgresql://lingering_moon_9343:44Alzy6eqsyf4ND@localhost:54320/lingering_moon_9343?sslmode=disable"

from app.database.db import engine, Base
import app.models.user
import app.models.bot
import app.models.trade
import app.models.position
import app.models.api_key
import app.models.signal
import app.models.subscription
import app.models.bot_state

print("Creating tables...")
Base.metadata.create_all(bind=engine)
print("TABLES BUILT!")

import psycopg2
conn = psycopg2.connect("postgresql://lingering_moon_9343:44Alzy6eqsyf4ND@localhost:54320/lingering_moon_9343?sslmode=disable")
cur = conn.cursor()
cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
print(cur.fetchall())
conn.close()
