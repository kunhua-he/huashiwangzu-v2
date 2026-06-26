"""S5+S9+D3: pgvector column, missing indexes, circuit breaker states table

Revision ID: 3b8f6e1a2c4d
Revises: 2a3f5e8b1c7d
Create Date: 2026-06-25 18:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
# revision identifiers, used by Alembic.
revision: str = '3b8f6e1a2c4d'
down_revision: Union[str, Sequence[str], None] = '2a3f5e8b1c7d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """S5: kb_chunks.embedding JSON→vector(1024) + index.
    S9: Indexes on framework_file_items, framework_file_folders,
        framework_file_shares, framework_file_json_versions,
        framework_file_json_patches, agent_messages, im_messages.
    D3: framework_circuit_breaker_states table.
    """

    # ── S5: pgvector column ────────────────────────────────────────────
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute(
        "ALTER TABLE kb_chunks "
        "ALTER COLUMN embedding TYPE vector(1024) "
        "USING embedding::text::vector(1024)"
    )
    op.create_index(
        "ix_kb_chunks_embedding_hnsw",
        "kb_chunks",
        [sa.text("embedding vector_cosine_ops")],
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 200},
    )

    # ── S9: framework_file_items indexes ────────────────────────────────
    op.create_index("ix_framework_file_items_owner_id", "framework_file_items", ["owner_id"])
    op.create_index("ix_framework_file_items_md5_hash", "framework_file_items", ["md5_hash"])
    op.create_index("ix_framework_file_items_owner_deleted",
                    "framework_file_items", ["owner_id", "deleted"])
    op.create_index("ix_framework_file_items_folder_id", "framework_file_items", ["folder_id"])

    # ── S9: framework_file_folders indexes ──────────────────────────────
    op.create_index("ix_framework_file_folders_owner_id", "framework_file_folders", ["owner_id"])
    op.create_index("ix_framework_file_folders_parent_id", "framework_file_folders", ["parent_id"])
    op.create_index("ix_framework_file_folders_owner_deleted",
                    "framework_file_folders", ["owner_id", "deleted"])

    # ── S9: framework_file_shares indexes ───────────────────────────────
    op.create_index("ix_framework_file_shares_file_id", "framework_file_shares", ["file_id"])
    op.create_index("ix_framework_file_shares_shared_with_user_id",
                    "framework_file_shares", ["shared_with_user_id"])
    op.create_index("ix_framework_file_shares_shared_by_owner_id",
                    "framework_file_shares", ["shared_by_owner_id"])

    # ── S9: framework_file_json_versions / _patches indexes ────────────
    op.create_index("ix_framework_file_json_versions_package_id",
                    "framework_file_json_versions", ["package_id"])
    op.create_index("ix_framework_file_json_patches_package_id",
                    "framework_file_json_patches", ["package_id"])

    # ── S9: agent_messages / im_messages indexes ───────────────────────
    op.create_index("ix_agent_messages_conversation_id",
                    "agent_messages", ["conversation_id"])
    op.create_index("ix_im_messages_conversation_id",
                    "im_messages", ["conversation_id"])

    # ── D3: circuit breaker states table ──────────────────────────────
    op.create_table("framework_circuit_breaker_states",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("key", sa.String(length=128), nullable=False, comment='"module:action" identifier'),
        sa.Column("state", sa.String(length=16), nullable=False, server_default="CLOSED",
                  comment="CLOSED | OPEN | HALF_OPEN"),
        sa.Column("failure_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_failure_time", sa.DateTime(timezone=True), nullable=True,
                  comment="Last failure timestamp (UTC)"),
        sa.Column("failure_threshold", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("recovery_timeout", sa.Float(), nullable=False, server_default="30.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
                  nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
                  nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key", name="uq_circuit_breaker_key"),
    )


def downgrade() -> None:
    """Reverse all changes."""
    # D3: drop table
    op.drop_table("framework_circuit_breaker_states")

    # S9: drop indexes
    op.drop_index("ix_im_messages_conversation_id")
    op.drop_index("ix_agent_messages_conversation_id")
    op.drop_index("ix_framework_file_json_patches_package_id")
    op.drop_index("ix_framework_file_json_versions_package_id")
    op.drop_index("ix_framework_file_shares_shared_by_owner_id")
    op.drop_index("ix_framework_file_shares_shared_with_user_id")
    op.drop_index("ix_framework_file_shares_file_id")
    op.drop_index("ix_framework_file_folders_owner_deleted")
    op.drop_index("ix_framework_file_folders_parent_id")
    op.drop_index("ix_framework_file_folders_owner_id")
    op.drop_index("ix_framework_file_items_folder_id")
    op.drop_index("ix_framework_file_items_owner_deleted")
    op.drop_index("ix_framework_file_items_md5_hash")
    op.drop_index("ix_framework_file_items_owner_id")

    # S5: drop hnsw index, revert column type
    op.drop_index("ix_kb_chunks_embedding_hnsw", table_name="kb_chunks",
                  postgresql_concurrently=False)
    op.execute(
        "ALTER TABLE kb_chunks "
        "ALTER COLUMN embedding TYPE json "
        "USING embedding::text::json"
    )
