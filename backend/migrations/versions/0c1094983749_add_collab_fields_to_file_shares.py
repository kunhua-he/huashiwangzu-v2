"""add_collab_fields_to_file_shares

Revision ID: 0c1094983749
Revises: d5dc41a139ab
Create Date: 2026-06-25 15:35:48.199192

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0c1094983749'
down_revision: Union[str, Sequence[str], None] = 'd5dc41a139ab'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """添加 file_shares 协作字段：scope/expiry/reason/publish/reshare，扩展 permission 为 read/edit/comment"""
    op.add_column('framework_file_shares', sa.Column('scope', postgresql.JSON(astext_type=sa.Text()), nullable=True, comment='Scope of share: e.g. {"types": ["file", "document_ir", "artifact", "evidence"]}'))
    op.add_column('framework_file_shares', sa.Column('expiry', sa.DateTime(timezone=True), nullable=True, comment='Share expiry time'))
    op.add_column('framework_file_shares', sa.Column('reason', sa.String(length=256), nullable=True, comment='Reason for sharing'))
    op.add_column('framework_file_shares', sa.Column('publish', sa.Boolean(), nullable=False, server_default=sa.text('false'), comment='Allow publish'))
    op.add_column('framework_file_shares', sa.Column('reshare', sa.Boolean(), nullable=False, server_default=sa.text('false'), comment='Allow reshare'))
    op.alter_column('framework_file_shares', 'permission',
               existing_type=sa.VARCHAR(length=16),
               comment='read | edit | comment',
               existing_comment='read | edit',
               existing_nullable=False)


def downgrade() -> None:
    """回退：删除协作字段，恢复 permission 注释"""
    op.alter_column('framework_file_shares', 'permission',
               existing_type=sa.VARCHAR(length=16),
               comment='read | edit',
               existing_comment='read | edit | comment',
               existing_nullable=False)
    op.drop_column('framework_file_shares', 'reshare')
    op.drop_column('framework_file_shares', 'publish')
    op.drop_column('framework_file_shares', 'reason')
    op.drop_column('framework_file_shares', 'expiry')
    op.drop_column('framework_file_shares', 'scope')
