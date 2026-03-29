"""add can_trade to users

Revision ID: b7c1d2e3f4a5
Revises: 9f2d1c6b7a8e
Create Date: 2026-03-20 16:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b7c1d2e3f4a5"
down_revision: Union[str, Sequence[str], None] = "9f2d1c6b7a8e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("can_trade", sa.Boolean(), nullable=True, server_default=sa.true()))
    op.execute("UPDATE users SET can_trade = true WHERE can_trade IS NULL")
    op.alter_column("users", "can_trade", nullable=False, server_default=None)


def downgrade() -> None:
    op.drop_column("users", "can_trade")

