import psycopg2
conn = psycopg2.connect("postgresql://lingering_moon_9343:44Alzy6eqsyf4ND@localhost:54320/lingering_moon_9343?sslmode=disable")
cur = conn.cursor()
try:
    cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS trading_paused BOOLEAN DEFAULT FALSE;")
    cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;")
    conn.commit()
    print("SUCCESSFULLY ADDED MISSING COLUMNS!")
except Exception as e:
    print(f"ERROR: {e}")
conn.close()
