"""add dom fields to trade_states

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-03-25 14:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, Sequence[str], None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("trade_states", sa.Column("dom_high", sa.Float(), nullable=True))
    op.add_column("trade_states", sa.Column("dom_low", sa.Float(), nullable=True))
    op.add_column("trade_states", sa.Column("dom_close", sa.Float(), nullable=True))
    op.add_column("trade_states", sa.Column("dom_length", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("trade_states", "dom_length")
    op.drop_column("trade_states", "dom_close")
    op.drop_column("trade_states", "dom_low")
    op.drop_column("trade_states", "dom_high")
