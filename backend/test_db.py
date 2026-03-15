import psycopg2
import os

DATABASE_URL = "postgresql://lingering_moon_9343:44Alzy6eqsyf4ND@localhost:54320/lingering_moon_9343?sslmode=disable"
try:
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
    tables = cur.fetchall()
    print("TABLES IN DATABASE:")
    if not tables:
        print("NO TABLES FOUND!")
    for table in tables:
        print(f"- {table[0]}")
        cur.execute(f"SELECT column_name, data_type FROM information_schema.columns WHERE table_name='{table[0]}'")
        columns = cur.fetchall()
        for col in columns:
            print(f"   {col[0]} ({col[1]})")
    conn.close()
except Exception as e:
    print(f"ERROR: {e}")
