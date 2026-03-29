"""normalize trade status remove executed

Revision ID: c9d8e7f6a5b4
Revises: b7c1d2e3f4a5
Create Date: 2026-03-20 17:10:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "c9d8e7f6a5b4"
down_revision: Union[str, Sequence[str], None] = "b7c1d2e3f4a5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Backfill legacy live rows into the normalized active status.
    op.execute("UPDATE trades SET status = 'OPEN' WHERE status = 'EXECUTED'")


def downgrade() -> None:
    # Best-effort reversal for legacy expectation.
    op.execute("UPDATE trades SET status = 'EXECUTED' WHERE status = 'OPEN'")

