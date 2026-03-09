"""ea_bridge

Revision ID: 8f2c1b2c3d4e
Revises: 63ac1a6ca08f
Create Date: 2026-03-09 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


# revision identifiers, used by Alembic.
revision: str = '8f2c1b2c3d4e'
down_revision: Union[str, None] = '63ac1a6ca08f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = Inspector.from_engine(bind)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def _index_exists(index_name: str, table_name: str) -> bool:
    bind = op.get_bind()
    inspector = Inspector.from_engine(bind)
    indexes = [idx['name'] for idx in inspector.get_indexes(table_name)]
    return index_name in indexes


def upgrade() -> None:
    # Users table
    if not _column_exists('users', 'ea_token'):
        op.add_column('users', sa.Column('ea_token', sa.String(), nullable=True))
    if not _column_exists('users', 'ea_last_seen'):
        op.add_column('users', sa.Column('ea_last_seen', sa.DateTime(), nullable=True))
        
    if not _index_exists('ix_users_ea_token', 'users'):
        op.create_index(op.f('ix_users_ea_token'), 'users', ['ea_token'], unique=True)
    
    if _column_exists('users', 'meta_account_id'):
        op.drop_column('users', 'meta_account_id')

    # Positions table
    if not _column_exists('positions', 'ea_picked_at'):
        op.add_column('positions', sa.Column('ea_picked_at', sa.DateTime(), nullable=True))
    if not _column_exists('positions', 'executed_price'):
        op.add_column('positions', sa.Column('executed_price', sa.Float(), nullable=True))


def downgrade() -> None:
    # Users table
    if not _column_exists('users', 'meta_account_id'):
        op.add_column('users', sa.Column('meta_account_id', sa.String(), nullable=True))
    
    if _index_exists('ix_users_ea_token', 'users'):
        op.drop_index(op.f('ix_users_ea_token'), table_name='users')
        
    if _column_exists('users', 'ea_token'):
        op.drop_column('users', 'ea_token')
    if _column_exists('users', 'ea_last_seen'):
        op.drop_column('users', 'ea_last_seen')

    # Positions table
    if _column_exists('positions', 'ea_picked_at'):
        op.drop_column('positions', 'ea_picked_at')
    if _column_exists('positions', 'executed_price'):
        op.drop_column('positions', 'executed_price')
