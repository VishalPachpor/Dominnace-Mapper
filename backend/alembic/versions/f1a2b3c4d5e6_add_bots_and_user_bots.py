"""add bots and user_bots tables

Revision ID: f1a2b3c4d5e6
Revises: c6ecbb5e618b
Create Date: 2026-03-13

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'f1a2b3c4d5e6'
down_revision = 'c6ecbb5e618b'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Tables were already created directly via SQL — this migration now just
    # stamps their existence for schema tracking purposes.
    # We use connection.execute with raw SQL to safely add columns if missing.
    bind = op.get_bind()
    
    # Add bot_id to trades if it doesn't exist
    result = bind.execute(sa.text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name='trades' AND column_name='bot_id'"
    ))
    if not result.fetchone():
        op.add_column('trades', sa.Column('bot_id', sa.String(), nullable=True))
    
    # Add bot_id to positions if it doesn't exist
    result = bind.execute(sa.text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name='positions' AND column_name='bot_id'"
    ))
    if not result.fetchone():
        op.add_column('positions', sa.Column('bot_id', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('positions', 'bot_id')
    op.drop_column('trades', 'bot_id')
    op.drop_table('user_bots')
    op.drop_table('bots')

