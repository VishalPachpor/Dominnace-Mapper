"""
Full Schema Audit - Compare SQLAlchemy models vs actual Postgres columns
and add any missing columns automatically.
"""
import psycopg2

conn = psycopg2.connect(
    "postgresql://lingering_moon_9343:44Alzy6eqsyf4ND@localhost:54320/lingering_moon_9343?sslmode=disable"
)
cur = conn.cursor()

# Get all tables
cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
tables = cur.fetchall()

print("=" * 60)
print("FULL DATABASE SCHEMA AUDIT")
print("=" * 60)

for (table,) in tables:
    cur.execute(f"SELECT column_name, data_type, column_default, is_nullable FROM information_schema.columns WHERE table_name='{table}' ORDER BY ordinal_position")
    cols = cur.fetchall()
    print(f"\n TABLE: {table}")
    for col_name, data_type, default, nullable in cols:
        print(f"   - {col_name:<30} {data_type:<25} default={default}  nullable={nullable}")

# Now check if missing columns exist that SQLAlchemy models expect
print("\n" + "=" * 60)
print("CHECKING FOR MISSING COLUMNS IN `users` TABLE")
print("=" * 60)

expected_users_cols = {
    "id": "character varying",
    "email": "character varying",
    "password_hash": "character varying",
    "exchange_api_key": "character varying",
    "exchange_secret_key": "character varying",
    "ea_token": "character varying",
    "ea_last_seen": "timestamp without time zone",
    "mt5_balance": "double precision",
    "mt5_equity": "double precision",
    "mt_login": "character varying",
    "mt_password_enc": "character varying",
    "mt_server": "character varying",
    "mt_broker": "character varying",
    "meta_account_id": "character varying",
    "mt_status": "character varying",
    "is_active": "boolean",
    "trading_paused": "boolean",
}

cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='users'")
existing = {r[0] for r in cur.fetchall()}

missing = [col for col in expected_users_cols if col not in existing]
if missing:
    print(f"\n MISSING COLUMNS: {missing}")
    for col in missing:
        suffix = ""
        if col in ["is_active", "trading_paused"]:
            suffix = "BOOLEAN DEFAULT FALSE"
        elif col in ["mt5_balance", "mt5_equity"]:
            suffix = "DOUBLE PRECISION DEFAULT 0.0"
        else:
            suffix = "VARCHAR"
        try:
            cur.execute(f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {col} {suffix};")
            print(f"   ✓ Added: {col}")
        except Exception as e:
            print(f"   ✗ Failed to add {col}: {e}")
    conn.commit()
    print("\n All missing columns added!")
else:
    print("\n ✓ All expected columns exist! Schema is correct.")

conn.close()
