"""Add full MetaApi broker credential fields to users table

Revision ID: a1b2c3d4e5f6
Revises: 7d160d3f4e8a
Create Date: 2026-03-12 23:40:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '7d160d3f4e8a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('mt_login', sa.String(50), nullable=True))
    op.add_column('users', sa.Column('mt_password_enc', sa.Text(), nullable=True))
    op.add_column('users', sa.Column('mt_server', sa.String(100), nullable=True))
    op.add_column('users', sa.Column('mt_broker', sa.String(100), nullable=True))
    op.add_column('users', sa.Column('mt_status', sa.String(30), server_default='disconnected', nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'mt_status')
    op.drop_column('users', 'mt_broker')
    op.drop_column('users', 'mt_server')
    op.drop_column('users', 'mt_password_enc')
    op.drop_column('users', 'mt_login')
