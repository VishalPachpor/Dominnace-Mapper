import uuid
import psycopg2

conn = psycopg2.connect('postgresql://lingering_moon_9343:44Alzy6eqsyf4ND@localhost:54320/lingering_moon_9343?sslmode=disable')
cur = conn.cursor()

bots_data = [
    (str(uuid.uuid4()), "DM BULL", "dm-bull", "Aggressive DOM-based momentum entries on low timeframes.", 0.1, True),
    (str(uuid.uuid4()), "SMC BUY", "smc-buy", "Smart Money Concepts: Order block and liquidity grabs.", 0.2, True),
    (str(uuid.uuid4()), "Breakout Pro", "breakout-pro", "High volatility breakout catcher.", 0.15, False)
]

# Insert bots
for b in bots_data:
    cur.execute("""
        INSERT INTO bots (id, name, slug, description, max_lot_size, is_active)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (slug) DO NOTHING;
    """, b)
    print(f"Added bot: {b[1]} ({b[2]})")

# Automatically subscribe the admin user to the bots
cur.execute("SELECT id FROM users LIMIT 1")
user_row = cur.fetchone()

if user_row:
    user_id = user_row[0]
    cur.execute("SELECT id FROM bots WHERE is_active = true")
    active_bot_ids = cur.fetchall()
    
    for (b_id,) in active_bot_ids:
        user_bot_id = str(uuid.uuid4())
        cur.execute("""
            INSERT INTO user_bots (id, user_id, bot_id, is_enabled)
            VALUES (%s, %s, %s, true)
            ON CONFLICT (user_id, bot_id) DO NOTHING;
        """, (user_bot_id, user_id, b_id))
    print(f"Subscribed user {user_id} to active bots")

conn.commit()
conn.close()
print("Seeding complete.")
