"""crypto_payments_nowpayments

Revision ID: 63ac1a6ca08f
Revises: 52a10d3f4e8b
Create Date: 2026-03-09 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


# revision identifiers, used by Alembic.
revision: str = '63ac1a6ca08f'
down_revision: Union[str, None] = '52a10d3f4e8b'
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
    # Add crypto payment fields — safely skip if already present
    if not _column_exists('subscriptions', 'payment_provider'):
        op.add_column('subscriptions', sa.Column('payment_provider', sa.String(), nullable=True))
    if not _column_exists('subscriptions', 'crypto_payment_id'):
        op.add_column('subscriptions', sa.Column('crypto_payment_id', sa.String(), nullable=True))
    if not _column_exists('subscriptions', 'crypto_tx_hash'):
        op.add_column('subscriptions', sa.Column('crypto_tx_hash', sa.String(), nullable=True))
    if not _column_exists('subscriptions', 'payment_currency'):
        op.add_column('subscriptions', sa.Column('payment_currency', sa.String(), nullable=True))

    # Create indexes safely
    if not _index_exists('ix_subscriptions_crypto_payment_id', 'subscriptions'):
        op.create_index(op.f('ix_subscriptions_crypto_payment_id'), 'subscriptions', ['crypto_payment_id'], unique=False)
    if not _index_exists('ix_subscriptions_crypto_tx_hash', 'subscriptions'):
        op.create_index(op.f('ix_subscriptions_crypto_tx_hash'), 'subscriptions', ['crypto_tx_hash'], unique=False)

    # Drop old Stripe columns safely
    if _index_exists('ix_subscriptions_stripe_customer_id', 'subscriptions'):
        op.drop_index('ix_subscriptions_stripe_customer_id', table_name='subscriptions')
    if _index_exists('ix_subscriptions_stripe_subscription_id', 'subscriptions'):
        op.drop_index('ix_subscriptions_stripe_subscription_id', table_name='subscriptions')
    if _column_exists('subscriptions', 'stripe_customer_id'):
        op.drop_column('subscriptions', 'stripe_customer_id')
    if _column_exists('subscriptions', 'stripe_subscription_id'):
        op.drop_column('subscriptions', 'stripe_subscription_id')


def downgrade() -> None:
    if _index_exists('ix_subscriptions_crypto_tx_hash', 'subscriptions'):
        op.drop_index(op.f('ix_subscriptions_crypto_tx_hash'), table_name='subscriptions')
    if _index_exists('ix_subscriptions_crypto_payment_id', 'subscriptions'):
        op.drop_index(op.f('ix_subscriptions_crypto_payment_id'), table_name='subscriptions')
    if _column_exists('subscriptions', 'payment_currency'):
        op.drop_column('subscriptions', 'payment_currency')
    if _column_exists('subscriptions', 'crypto_tx_hash'):
        op.drop_column('subscriptions', 'crypto_tx_hash')
    if _column_exists('subscriptions', 'crypto_payment_id'):
        op.drop_column('subscriptions', 'crypto_payment_id')
    if _column_exists('subscriptions', 'payment_provider'):
        op.drop_column('subscriptions', 'payment_provider')
