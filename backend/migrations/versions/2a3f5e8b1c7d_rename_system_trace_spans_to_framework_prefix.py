"""rename_system_trace_spans_to_framework_prefix

Revision ID: 2a3f5e8b1c7d
Revises: 0c1094983749
Create Date: 2026-06-25 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2a3f5e8b1c7d'
down_revision: Union[str, Sequence[str], None] = '0c1094983749'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.rename_table('system_trace_spans', 'framework_system_trace_spans')


def downgrade() -> None:
    op.rename_table('framework_system_trace_spans', 'system_trace_spans')
