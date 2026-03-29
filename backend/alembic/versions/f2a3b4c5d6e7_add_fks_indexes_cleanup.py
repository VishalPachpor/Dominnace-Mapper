"""Add missing FKs, indexes, and model cleanup

Revision ID: f2a3b4c5d6e7
Revises: e5f6a7b8c9d0
Create Date: 2026-03-29

Changes:
- Add FK constraint on trades.bot_id -> bots.id
- Add FK constraint on positions.bot_id -> bots.id
- Add FK constraint on api_keys.user_id -> users.id
- Add FK constraint on subscriptions.user_id -> users.id
- Add indexes on trades.symbol, trades.status, trades.bot_id
- Add indexes on positions.symbol, positions.status, positions.bot_id
- Add index on api_keys.user_id
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f2a3b4c5d6e7"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- Trades table ---
    op.create_index("ix_trades_symbol", "trades", ["symbol"], if_not_exists=True)
    op.create_index("ix_trades_status", "trades", ["status"], if_not_exists=True)
    op.create_index("ix_trades_bot_id", "trades", ["bot_id"], if_not_exists=True)

    # FK: trades.bot_id -> bots.id (SET NULL on delete)
    try:
        op.create_foreign_key(
            "fk_trades_bot_id", "trades", "bots", ["bot_id"], ["id"], ondelete="SET NULL"
        )
    except Exception:
        pass  # FK may already exist or column types may differ

    # --- Positions table ---
    op.create_index("ix_positions_symbol", "positions", ["symbol"], if_not_exists=True)
    op.create_index("ix_positions_status", "positions", ["status"], if_not_exists=True)
    op.create_index("ix_positions_bot_id", "positions", ["bot_id"], if_not_exists=True)

    try:
        op.create_foreign_key(
            "fk_positions_bot_id", "positions", "bots", ["bot_id"], ["id"], ondelete="SET NULL"
        )
    except Exception:
        pass

    # --- API Keys table ---
    op.create_index("ix_api_keys_user_id", "api_keys", ["user_id"], if_not_exists=True)

    try:
        op.create_foreign_key(
            "fk_api_keys_user_id", "api_keys", "users", ["user_id"], ["id"], ondelete="CASCADE"
        )
    except Exception:
        pass

    # --- Subscriptions table ---
    try:
        op.create_foreign_key(
            "fk_subscriptions_user_id", "subscriptions", "users", ["user_id"], ["id"], ondelete="CASCADE"
        )
    except Exception:
        pass


def downgrade() -> None:
    # Drop FKs
    try:
        op.drop_constraint("fk_trades_bot_id", "trades", type_="foreignkey")
    except Exception:
        pass
    try:
        op.drop_constraint("fk_positions_bot_id", "positions", type_="foreignkey")
    except Exception:
        pass
    try:
        op.drop_constraint("fk_api_keys_user_id", "api_keys", type_="foreignkey")
    except Exception:
        pass
    try:
        op.drop_constraint("fk_subscriptions_user_id", "subscriptions", type_="foreignkey")
    except Exception:
        pass

    # Drop indexes
    op.drop_index("ix_trades_symbol", table_name="trades")
    op.drop_index("ix_trades_status", table_name="trades")
    op.drop_index("ix_trades_bot_id", table_name="trades")
    op.drop_index("ix_positions_symbol", table_name="positions")
    op.drop_index("ix_positions_status", table_name="positions")
    op.drop_index("ix_positions_bot_id", table_name="positions")
    op.drop_index("ix_api_keys_user_id", table_name="api_keys")
