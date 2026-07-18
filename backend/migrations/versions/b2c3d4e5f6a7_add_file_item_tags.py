"""Add framework_file_item_tags for multi-user Finder tags.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-07-18 12:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "framework_file_item_tags" not in inspector.get_table_names():
        op.create_table(
            "framework_file_item_tags",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("owner_id", sa.BigInteger(), nullable=False),
            sa.Column("item_type", sa.String(length=16), nullable=False),
            sa.Column("item_id", sa.Integer(), nullable=False),
            sa.Column("tag", sa.String(length=32), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.UniqueConstraint(
                "owner_id",
                "item_type",
                "item_id",
                "tag",
                name="ux_framework_file_item_tags_owner_item_tag",
            ),
        )

    existing_indexes = {idx["name"] for idx in inspector.get_indexes("framework_file_item_tags")}
    if "ix_framework_file_item_tags_owner_id" not in existing_indexes:
        op.create_index("ix_framework_file_item_tags_owner_id", "framework_file_item_tags", ["owner_id"])
    if "ix_framework_file_item_tags_item_id" not in existing_indexes:
        op.create_index("ix_framework_file_item_tags_item_id", "framework_file_item_tags", ["item_id"])
    if "ix_framework_file_item_tags_owner_item" not in existing_indexes:
        op.create_index(
            "ix_framework_file_item_tags_owner_item",
            "framework_file_item_tags",
            ["owner_id", "item_type", "item_id"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "framework_file_item_tags" not in inspector.get_table_names():
        return
    existing_indexes = {idx["name"] for idx in inspector.get_indexes("framework_file_item_tags")}
    if "ix_framework_file_item_tags_owner_item" in existing_indexes:
        op.drop_index("ix_framework_file_item_tags_owner_item", table_name="framework_file_item_tags")
    if "ix_framework_file_item_tags_item_id" in existing_indexes:
        op.drop_index("ix_framework_file_item_tags_item_id", table_name="framework_file_item_tags")
    if "ix_framework_file_item_tags_owner_id" in existing_indexes:
        op.drop_index("ix_framework_file_item_tags_owner_id", table_name="framework_file_item_tags")
    op.drop_table("framework_file_item_tags")
