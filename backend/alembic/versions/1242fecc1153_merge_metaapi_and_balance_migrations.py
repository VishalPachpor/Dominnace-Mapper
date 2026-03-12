"""Merge MetaApi and Balance migrations

Revision ID: 1242fecc1153
Revises: a1b2c3d4e5f6, c6ecbb5e618b
Create Date: 2026-03-13 00:08:23.413661

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1242fecc1153'
down_revision: Union[str, Sequence[str], None] = ('a1b2c3d4e5f6', 'c6ecbb5e618b')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column('meta_account_id', sa.String(100), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'meta_account_id')
