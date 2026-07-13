"""Add framework file image derivatives.

Revision ID: 7f1a2b3c4d5e
Revises: 6e0f1a2b3c4d
Create Date: 2026-07-13 14:50:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "7f1a2b3c4d5e"
down_revision: Union[str, Sequence[str], None] = "6e0f1a2b3c4d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_name = "framework_file_derivatives"

    if table_name not in inspector.get_table_names():
        op.create_table(
            table_name,
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "file_id",
                sa.Integer(),
                sa.ForeignKey("framework_file_items.id", ondelete="CASCADE"),
                nullable=False,
                comment="Original framework file id",
            ),
            sa.Column("kind", sa.String(length=32), nullable=False, comment="standard_image / preview"),
            sa.Column("storage_path", sa.String(length=512), nullable=False, comment="Derivative path relative to upload root"),
            sa.Column("mime_type", sa.String(length=128), nullable=False, server_default="image/jpeg"),
            sa.Column("size", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("md5_hash", sa.String(length=32), nullable=False, server_default=""),
            sa.Column("width", sa.Integer(), nullable=True),
            sa.Column("height", sa.Integer(), nullable=True),
            sa.Column("source_md5_hash", sa.String(length=32), nullable=True),
            sa.Column("metadata_json", postgresql.JSONB(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.UniqueConstraint("file_id", "kind", name="ux_framework_file_derivatives_file_kind"),
        )

    op.alter_column(table_name, "mime_type", server_default="image/jpeg")
    op.alter_column(table_name, "size", server_default="0")
    op.alter_column(table_name, "md5_hash", server_default="")

    indexes = {item["name"] for item in inspector.get_indexes(table_name)}
    if "ix_framework_file_derivatives_file_id" not in indexes:
        op.create_index(
            "ix_framework_file_derivatives_file_id",
            table_name,
            ["file_id"],
        )

    uniques = {item["name"] for item in inspector.get_unique_constraints(table_name)}
    if "ux_framework_file_derivatives_file_kind" not in uniques:
        op.create_unique_constraint(
            "ux_framework_file_derivatives_file_kind",
            table_name,
            ["file_id", "kind"],
        )

    foreign_keys = {
        tuple(item.get("constrained_columns") or ())
        for item in inspector.get_foreign_keys(table_name)
    }
    if ("file_id",) not in foreign_keys:
        op.create_foreign_key(
            "framework_file_derivatives_file_id_fkey",
            table_name,
            "framework_file_items",
            ["file_id"],
            ["id"],
            ondelete="CASCADE",
        )


def downgrade() -> None:
    op.drop_index("ix_framework_file_derivatives_file_id", table_name="framework_file_derivatives")
    op.drop_table("framework_file_derivatives")
