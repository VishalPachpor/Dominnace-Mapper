"""add is_admin to users

Revision ID: a0b1c2d3e4f5
Revises: 723b33ea6b47
Create Date: 2026-03-14

"""
from alembic import op
import sqlalchemy as sa

revision = 'a0b1c2d3e4f5'
down_revision = '723b33ea6b47'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('is_admin', sa.Boolean(), server_default='false', nullable=False))


def downgrade():
    op.drop_column('users', 'is_admin')
