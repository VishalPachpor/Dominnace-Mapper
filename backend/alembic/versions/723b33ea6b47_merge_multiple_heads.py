"""merge multiple heads

Revision ID: 723b33ea6b47
Revises: 1242fecc1153, f1a2b3c4d5e6
Create Date: 2026-03-14 17:24:06.147998

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '723b33ea6b47'
down_revision: Union[str, Sequence[str], None] = ('1242fecc1153', 'f1a2b3c4d5e6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
