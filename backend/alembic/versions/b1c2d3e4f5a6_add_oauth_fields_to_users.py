"""add oauth fields to users

Revision ID: b1c2d3e4f5a6
Revises: a0b1c2d3e4f5
Create Date: 2026-03-14

"""
from alembic import op
import sqlalchemy as sa

revision = 'b1c2d3e4f5a6'
down_revision = 'a0b1c2d3e4f5'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('oauth_provider', sa.String(20), nullable=True))
    op.add_column('users', sa.Column('oauth_sub', sa.String(255), nullable=True))
    op.add_column('users', sa.Column('full_name', sa.String(200), nullable=True))
    op.add_column('users', sa.Column('avatar_url', sa.String(500), nullable=True))
    op.create_unique_constraint('uq_users_oauth_sub', 'users', ['oauth_sub'])
    # Allow password_hash to be null for OAuth-only users
    op.alter_column('users', 'password_hash', existing_type=sa.String(), nullable=True)


def downgrade():
    op.alter_column('users', 'password_hash', existing_type=sa.String(), nullable=False)
    op.drop_constraint('uq_users_oauth_sub', 'users', type_='unique')
    op.drop_column('users', 'avatar_url')
    op.drop_column('users', 'full_name')
    op.drop_column('users', 'oauth_sub')
    op.drop_column('users', 'oauth_provider')
