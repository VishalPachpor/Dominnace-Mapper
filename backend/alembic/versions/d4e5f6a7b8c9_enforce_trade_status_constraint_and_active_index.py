"""enforce trade status constraint and active index

Revision ID: d4e5f6a7b8c9
Revises: c9d8e7f6a5b4
Create Date: 2026-03-20 17:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "c9d8e7f6a5b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Normalize any legacy status values before enforcing the constraint.
    op.execute("UPDATE trades SET status = 'OPEN' WHERE status IN ('EXECUTED', 'PENDING')")
    op.execute("UPDATE trades SET status = 'EXECUTION_FAILED' WHERE status IN ('FAILED')")
    op.execute("UPDATE trades SET status = 'EXECUTION_FAILED' WHERE status IS NULL")

    op.create_check_constraint(
        "trades_status_check",
        "trades",
        "status IN ('OPEN','CLOSING','CLOSED','EXECUTION_FAILED')",
    )

    op.create_index(
        "idx_trades_active",
        "trades",
        ["user_id", "status"],
        unique=False,
        postgresql_where=sa.text("status IN ('OPEN','CLOSING')"),
    )


def downgrade() -> None:
    op.drop_index("idx_trades_active", table_name="trades")
    op.drop_constraint("trades_status_check", "trades", type_="check")

