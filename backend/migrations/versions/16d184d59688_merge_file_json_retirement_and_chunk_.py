"""merge file json retirement and chunk embeddings heads

Revision ID: 16d184d59688
Revises: 132d955fc2d4, 9f1a2b3c4d5e
Create Date: 2026-07-11 11:47:46.712313

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '16d184d59688'
down_revision: Union[str, Sequence[str], None] = ('132d955fc2d4', '9f1a2b3c4d5e')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
