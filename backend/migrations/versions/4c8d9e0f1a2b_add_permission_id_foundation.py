"""Add permission ID and capability policy foundation.

Revision ID: 4c8d9e0f1a2b
Revises: 16d184d59688
Create Date: 2026-07-13 12:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "4c8d9e0f1a2b"
down_revision: Union[str, Sequence[str], None] = "16d184d59688"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES = {
    "framework_permissions",
    "framework_permission_sets",
    "framework_permission_set_members",
    "framework_user_permission_grants",
    "framework_user_permission_set_grants",
    "framework_capability_identities",
    "framework_capability_permission_requirements",
}


def upgrade() -> None:
    existing = _TABLES & set(sa.inspect(op.get_bind()).get_table_names())
    if existing == _TABLES:
        # The live application runs metadata.create_all() before Alembic in
        # some development reload paths. Treat a complete matching schema as
        # already materialized, while refusing to bless a partial schema.
        return
    if existing:
        missing = sorted(_TABLES - existing)
        raise RuntimeError(f"Partial permission schema exists; missing tables: {missing}")

    op.create_table(
        "framework_permissions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("stable_key", sa.String(length=128), nullable=False),
        sa.Column("display_name", sa.String(length=128), nullable=False),
        sa.Column("scope", sa.String(length=64), nullable=False, server_default="system"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stable_key"),
    )
    op.create_table(
        "framework_permission_sets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("stable_key", sa.String(length=128), nullable=False),
        sa.Column("display_name", sa.String(length=128), nullable=False),
        sa.Column("system_managed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stable_key"),
    )
    op.create_table(
        "framework_capability_identities",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("module_key", sa.String(length=128), nullable=False),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("permission_match_mode", sa.String(length=8), nullable=False, server_default="all"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("module_key", "action"),
    )
    op.create_index("ix_framework_capability_identities_module_key", "framework_capability_identities", ["module_key"])
    op.create_table(
        "framework_permission_set_members",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("permission_set_id", sa.Integer(), nullable=False),
        sa.Column("permission_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["permission_id"], ["framework_permissions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["permission_set_id"], ["framework_permission_sets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("permission_set_id", "permission_id"),
    )
    op.create_index("ix_framework_permission_set_members_permission_id", "framework_permission_set_members", ["permission_id"])
    op.create_index("ix_framework_permission_set_members_set_id", "framework_permission_set_members", ["permission_set_id"])
    op.create_table(
        "framework_user_permission_grants",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("permission_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["permission_id"], ["framework_permissions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["framework_user_accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "permission_id"),
    )
    op.create_index("ix_framework_user_permission_grants_permission_id", "framework_user_permission_grants", ["permission_id"])
    op.create_index("ix_framework_user_permission_grants_user_id", "framework_user_permission_grants", ["user_id"])
    op.create_table(
        "framework_user_permission_set_grants",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("permission_set_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["permission_set_id"], ["framework_permission_sets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["framework_user_accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "permission_set_id"),
    )
    op.create_index("ix_framework_user_permission_set_grants_set_id", "framework_user_permission_set_grants", ["permission_set_id"])
    op.create_index("ix_framework_user_permission_set_grants_user_id", "framework_user_permission_set_grants", ["user_id"])
    op.create_table(
        "framework_capability_permission_requirements",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("capability_id", sa.Integer(), nullable=False),
        sa.Column("permission_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["capability_id"], ["framework_capability_identities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["permission_id"], ["framework_permissions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("capability_id", "permission_id"),
    )
    op.create_index("ix_framework_capability_permission_req_capability", "framework_capability_permission_requirements", ["capability_id"])
    op.create_index("ix_framework_capability_permission_req_permission", "framework_capability_permission_requirements", ["permission_id"])


def downgrade() -> None:
    op.drop_table("framework_capability_permission_requirements")
    op.drop_table("framework_user_permission_set_grants")
    op.drop_table("framework_user_permission_grants")
    op.drop_table("framework_permission_set_members")
    op.drop_index("ix_framework_capability_identities_module_key", table_name="framework_capability_identities")
    op.drop_table("framework_capability_identities")
    op.drop_table("framework_permission_sets")
    op.drop_table("framework_permissions")
