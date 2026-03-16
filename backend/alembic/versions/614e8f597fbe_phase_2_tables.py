"""Phase 2 Tables

Revision ID: 614e8f597fbe
Revises: b1c2d3e4f5a6
Create Date: 2026-03-16 20:50:21.118544

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '614e8f597fbe'
down_revision: Union[str, Sequence[str], None] = 'b1c2d3e4f5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ─── New Tables ───

    # 1. Plans
    op.create_table(
        'plans',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('max_strategies', sa.Integer(), nullable=True),
        sa.Column('price_usd', sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_plans_name'), 'plans', ['name'], unique=True)

    # 2. Plan Strategies (Junction)
    op.create_table(
        'plan_strategies',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('plan_id', sa.String(), nullable=False),
        sa.Column('bot_id', sa.String(), nullable=False),
        sa.ForeignKeyConstraint(['bot_id'], ['bots.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['plan_id'], ['plans.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_plan_strategies_bot_id'), 'plan_strategies', ['bot_id'], unique=False)
    op.create_index(op.f('ix_plan_strategies_plan_id'), 'plan_strategies', ['plan_id'], unique=False)

    # 3. Trade States
    op.create_table(
        'trade_states',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('symbol', sa.String(), nullable=False),
        sa.Column('bot_slug', sa.String(), nullable=False),
        sa.Column('entry_price', sa.Float(), nullable=False),
        sa.Column('sl_price', sa.Float(), nullable=False),
        sa.Column('tp_price', sa.Float(), nullable=False),
        sa.Column('be_trigger', sa.Float(), nullable=False),
        sa.Column('side', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('reversal_used', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_trade_states_bot_slug'), 'trade_states', ['bot_slug'], unique=False)
    op.create_index(op.f('ix_trade_states_status'), 'trade_states', ['status'], unique=False)
    op.create_index(op.f('ix_trade_states_symbol'), 'trade_states', ['symbol'], unique=False)
    op.create_index(op.f('ix_trade_states_user_id'), 'trade_states', ['user_id'], unique=False)

    # ─── Column Additions ───

    # Bots: add metadata
    op.add_column('bots', sa.Column('risk_level', sa.String(), nullable=True, server_default='Medium'))
    op.add_column('bots', sa.Column('timeframe', sa.String(), nullable=True, server_default='15m'))
    op.add_column('bots', sa.Column('supported_symbols', sa.String(), nullable=True, server_default='All'))

    # Users: add plan_id
    op.add_column('users', sa.Column('plan_id', sa.String(), nullable=True))
    op.create_index(op.f('ix_users_plan_id'), 'users', ['plan_id'], unique=False)
    op.create_foreign_key('fk_users_plan_id_plans', 'users', 'plans', ['plan_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    op.drop_constraint('fk_users_plan_id_plans', 'users', type_='foreignkey')
    op.drop_index(op.f('ix_users_plan_id'), table_name='users')
    op.drop_column('users', 'plan_id')
    
    op.drop_column('bots', 'supported_symbols')
    op.drop_column('bots', 'timeframe')
    op.drop_column('bots', 'risk_level')

    op.drop_table('trade_states')
    op.drop_table('plan_strategies')
    op.drop_table('plans')
