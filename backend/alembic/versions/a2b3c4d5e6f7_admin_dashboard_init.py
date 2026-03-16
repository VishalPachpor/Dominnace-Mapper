"""admin_dashboard_init

Revision ID: a2b3c4d5e6f7
Revises: f11e28f3f861
Create Date: 2026-03-16 22:50:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a2b3c4d5e6f7'
down_revision: Union[str, Sequence[str], None] = 'f11e28f3f861'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # Users table updates
    op.add_column('users', sa.Column('status', sa.String(length=20), nullable=True))
    op.add_column('users', sa.Column('created_at', sa.DateTime(), nullable=True))
    op.add_column('users', sa.Column('last_login', sa.DateTime(), nullable=True))
    
    # Set defaults for existing users
    op.execute("UPDATE users SET status = 'active' WHERE status IS NULL")
    op.execute("UPDATE users SET created_at = NOW() WHERE created_at IS NULL")

    # Strategy Stats table
    op.create_table('strategy_stats',
        sa.Column('bot_slug', sa.String(), nullable=False),
        sa.Column('total_trades', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('total_pnl', sa.Float(), nullable=True, server_default='0.0'),
        sa.Column('wins', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('losses', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('last_updated', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('bot_slug')
    )

    # Platform Metrics table
    op.create_table('platform_metrics',
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('signals', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('trades', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('new_users', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('revenue', sa.Float(), nullable=True, server_default='0.0'),
        sa.PrimaryKeyConstraint('date')
    )

    # Admin Logs table
    op.create_table('admin_logs',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('admin_id', sa.String(), nullable=False),
        sa.Column('action', sa.String(), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['admin_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_admin_logs_admin_id'), 'admin_logs', ['admin_id'], unique=False)

def downgrade() -> None:
    op.drop_index(op.f('ix_admin_logs_admin_id'), table_name='admin_logs')
    op.drop_table('admin_logs')
    op.drop_table('platform_metrics')
    op.drop_table('strategy_stats')
    op.drop_column('users', 'last_login')
    op.drop_column('users', 'created_at')
    op.drop_column('users', 'status')
