"""Add missing OAuth columns to the production database."""
import psycopg2

conn = psycopg2.connect(
    "postgresql://lingering_moon_9343:44Alzy6eqsyf4ND@localhost:54320/lingering_moon_9343?sslmode=disable"
)
cur = conn.cursor()

columns = [
    ("oauth_provider", "VARCHAR(20)"),
    ("oauth_sub", "VARCHAR UNIQUE"),
    ("full_name", "VARCHAR(200)"),
    ("avatar_url", "VARCHAR"),
]

for col_name, col_type in columns:
    try:
        cur.execute(f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {col_name} {col_type};")
        print(f"  ✓ Added column: {col_name}")
    except Exception as e:
        print(f"  ✗ Failed: {col_name} — {e}")
        conn.rollback()

conn.commit()
print("\n✅ All OAuth columns added to production DB!")
conn.close()
