"""add monitor reliability columns

Revision ID: 9f2d1c6b7a8e
Revises: 83c266475654
Create Date: 2026-03-20 18:25:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9f2d1c6b7a8e"
down_revision: Union[str, Sequence[str], None] = "83c266475654"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("trades", sa.Column("last_synced_at", sa.DateTime(), nullable=True))
    op.add_column("trades", sa.Column("retry_count", sa.Integer(), nullable=True, server_default="0"))
    op.add_column("trade_states", sa.Column("last_checked_at", sa.DateTime(), nullable=True))

    op.create_index("ix_trades_last_synced_at", "trades", ["last_synced_at"], unique=False)

    op.execute("UPDATE trades SET retry_count = 0 WHERE retry_count IS NULL")
    op.alter_column("trades", "retry_count", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_trades_last_synced_at", table_name="trades")
    op.drop_column("trade_states", "last_checked_at")
    op.drop_column("trades", "retry_count")
    op.drop_column("trades", "last_synced_at")

