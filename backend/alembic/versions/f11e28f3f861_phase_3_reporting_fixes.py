"""phase_3_reporting_fixes

Revision ID: f11e28f3f861
Revises: 614e8f597fbe
Create Date: 2026-03-16 21:10:40.680168

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f11e28f3f861'
down_revision: Union[str, Sequence[str], None] = '614e8f597fbe'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add columns to positions table
    op.add_column('positions', sa.Column('exit_price', sa.Float(), nullable=True))
    op.add_column('positions', sa.Column('pnl', sa.Float(), nullable=True))
    op.add_column('positions', sa.Column('closed_at', sa.DateTime(), nullable=True))
    
    # Add columns to trade_states table
    op.add_column('trade_states', sa.Column('position_id', sa.String(), nullable=True))
    op.create_index(op.f('ix_trade_states_position_id'), 'trade_states', ['position_id'], unique=False)


def downgrade() -> None:
    # Drop columns from trade_states
    op.drop_index(op.f('ix_trade_states_position_id'), table_name='trade_states')
    op.drop_column('trade_states', 'position_id')
    
    # Drop columns from positions
    op.drop_column('positions', 'closed_at')
    op.drop_column('positions', 'pnl')
    op.drop_column('positions', 'exit_price')
