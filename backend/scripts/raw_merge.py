import sys
import os

# Set up path to import db
sys.path.insert(0, os.path.abspath("/app"))

from app.database.db import SessionLocal
from sqlalchemy import text

def run_merge():
    db = SessionLocal()
    try:
        print("Starting duplicate finder phase...")
        res = db.execute(text("""
            SELECT LOWER(email) as l_email, COUNT(*), ARRAY_AGG(id ORDER BY id ASC) as ids
            FROM users
            GROUP BY LOWER(email)
            HAVING COUNT(*) > 1
        """))
        duplicates = res.fetchall()
        
        if not duplicates:
            print("No case-insensitive duplicate emails found.")
        
        for row in duplicates:
            email = row[0]
            ids = row[2]
            primary_id = ids[0]
            duplicate_ids = ids[1:]
            print(f"Found duplicates for {email}. Primary: {primary_id}, Duplicates: {duplicate_ids}")
            
            for dup_id in duplicate_ids:
                print(f"Merging {dup_id} into {primary_id}...")
                
                # Transfer missing fields from duplicate to primary
                fields = ['mt_login', 'mt_password_enc', 'mt_server', 'mt_broker', 'meta_account_id', 'mt_status', 'full_name', 'avatar_url', 'exchange_api_key', 'exchange_secret_key']
                
                pri_data = db.execute(text(f"SELECT * FROM users WHERE id='{primary_id}'")).fetchone()
                dup_data = db.execute(text(f"SELECT * FROM users WHERE id='{dup_id}'")).fetchone()
                
                for field in fields:
                    old_val = getattr(pri_data, field, None)
                    new_val = getattr(dup_data, field, None)
                    # Use generic setattr like syntax via sql
                    if new_val is not None and old_val is None:
                        if isinstance(new_val, str):
                            escaped_val = new_val.replace("'", "''")
                            db.execute(text(f"UPDATE users SET {field} = '{escaped_val}' WHERE id = '{primary_id}'"))
                        else:
                            db.execute(text(f"UPDATE users SET {field} = :val WHERE id = '{primary_id}'"), {"val": new_val})

                # Update related tables
                tables = ["oauth_accounts", "positions", "trades", "subscriptions", "user_bots", "api_keys", "admin_logs", "bot_states", "trade_states"]
                for table in tables:
                    try:
                        with db.begin_nested():
                            db.execute(text(f"UPDATE {table} SET user_id = :p_id WHERE user_id = :d_id"), {"p_id": primary_id, "d_id": dup_id})
                    except Exception as e:
                        print(f"Skipped updating {table}: {e}")
                
                # Hard delete duplicate
                db.execute(text(f"DELETE FROM users WHERE id = '{dup_id}'"))
                
        db.commit()
        print("Merge phase completed successfully.")
        
        print("Starting email normalization phase...")
        db.execute(text("UPDATE users SET email = LOWER(email) WHERE email != LOWER(email)"))
        db.commit()
        print("Emails normalized successfully.")

    except Exception as e:
        db.rollback()
        print(f"Merge Failed: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    run_merge()
