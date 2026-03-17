import sys
import os
from sqlalchemy import text
from typing import List

# Add the backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database.db import SessionLocal
from app.models.user import User
from app.models.oauth_account import OAuthAccount

def merge_users(primary_id: str, duplicate_id: str):
    db = SessionLocal()
    try:
        # Use session.get() for newer SQLAlchemy versions or session.query(User).get()
        primary = db.query(User).filter(User.id == primary_id).first()
        duplicate = db.query(User).filter(User.id == duplicate_id).first()

        if not primary or not duplicate:
            print(f"Error: One or both users not found. Primary: {primary_id if primary else 'NOT FOUND'}, Duplicate: {duplicate_id if duplicate else 'NOT FOUND'}")
            return

        if primary_id == duplicate_id:
            print("Error: Primary and Duplicate IDs are the same.")
            return

        print(f"Merging User {duplicate.email} (ID: {duplicate_id}) into {primary.email} (ID: {primary_id})")

        # Check if both have OAuth accounts (Safeguard)
        pri_oauth_count = db.query(OAuthAccount).filter(OAuthAccount.user_id == primary_id).count()
        dup_oauth_count = db.query(OAuthAccount).filter(OAuthAccount.user_id == duplicate_id).count()
        
        if pri_oauth_count > 0 and dup_oauth_count > 0:
            print("⚠️ WARNING: Both accounts have linked OAuth identities. Manual review suggested.")
            # We still proceed if forced, but for now we link them all to primary

        # Tables to update
        tables_to_update = [
            ("oauth_accounts", "user_id"),
            ("positions", "user_id"),
            ("trades", "user_id"),
            ("subscriptions", "user_id"),
            ("user_bots", "user_id"),
            ("api_keys", "user_id"),
            ("admin_logs", "user_id"),
            ("bot_states", "user_id"),
            ("trade_states", "user_id"),
        ]

        for table, column in tables_to_update:
            try:
                # Check for existing records
                count_res = db.execute(text(f"SELECT COUNT(*) FROM {table} WHERE {column} = :dup_id"), {"dup_id": duplicate_id})
                count = count_res.scalar()
                if count > 0:
                    print(f"Moving {count} records from {table}.{column}")
                    db.execute(text(f"UPDATE {table} SET {column} = :pri_id WHERE {column} = :dup_id"), {"pri_id": primary_id, "dup_id": duplicate_id})
            except Exception as e:
                # Some tables might not exist or use different column names
                # print(f"Note: Skipping/Error on table {table}: {e}")
                pass

        # Transfer User-specific data if primary is empty
        fields_to_transfer = [
            'mt_login', 'mt_password_enc', 'mt_server', 'mt_broker', 
            'meta_account_id', 'mt_status', 'full_name', 'avatar_url',
            'exchange_api_key', 'exchange_secret_key'
        ]
        
        updated_primary = False
        for field in fields_to_transfer:
            dup_val = getattr(duplicate, field, None)
            pri_val = getattr(primary, field, None)
            if dup_val and not pri_val:
                print(f"Transferring field: {field}")
                setattr(primary, field, dup_val)
                updated_primary = True
        
        if updated_primary:
            db.add(primary)

        # Delete the duplicate user
        print(f"Deleting duplicate user: {duplicate.email} (ID: {duplicate_id})")
        db.delete(duplicate)
        
        db.commit()
        print("✅ Merge completed successfully.")
    except Exception as e:
        db.rollback()
        print(f"❌ Merge failed: {e}")
    finally:
        db.close()

def find_duplicates():
    db = SessionLocal()
    try:
        result = db.execute(text("SELECT email, COUNT(*) FROM users GROUP BY email HAVING COUNT(*) > 1"))
        duplicates = result.all()
        
        if not duplicates:
            print("No duplicate emails found.")
            return

        for email, count in duplicates:
            print(f"\nDuplicate found for email: {email} ({count} accounts)")
            users = db.query(User).filter(User.email == email).order_by(User.created_at).all()
            for i, user in enumerate(users):
                password_status = "Has Password" if user.password_hash else "No Password"
                print(f"  [{i}] ID: {user.id} | Created: {user.created_at} | {password_status}")
    finally:
        db.close()

if __name__ == "__main__":
    if len(sys.argv) == 1:
        find_duplicates()
        print("\nTo merge: python3 scripts/merge_users.py <primary_id> <duplicate_id>")
    elif len(sys.argv) == 3:
        merge_users(sys.argv[1], sys.argv[2])
    else:
        print("Usage:")
        print("  Find duplicates: python3 scripts/merge_users.py")
        print("  Merge accounts:  python3 scripts/merge_users.py <primary_id> <duplicate_id>")
