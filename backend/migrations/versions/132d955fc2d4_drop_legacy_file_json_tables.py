"""Drop legacy framework_file_json_* tables (Content-Package old schema).

The ORM models, old patch/rollback endpoints, and runtime methods were
already removed in an earlier round.  This migration completes retirement
by dropping the four physical tables at the Alembic head.

Downgrade recreates the tables for rollback safety but should not be
needed — the old code is gone.

Revision ID: 132d955fc2d4
Revises: 3b8f6e1a2c4d
Create Date: 2026-06-30 18:47:01.187411

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '132d955fc2d4'
down_revision: Union[str, Sequence[str], None] = '3b8f6e1a2c4d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Drop legacy file_json tables in FK-safe order."""

    # 1. Drop circular FK: packages → versions (must go before versions)
    op.execute(
        "ALTER TABLE framework_file_json_packages "
        "DROP CONSTRAINT IF EXISTS fk_framework_file_json_packages_current_version"
    )

    # 2. Drop indexes created by prior migration (3b8f6e1a2c4d)
    op.drop_index("ix_framework_file_json_patches_package_id",
                  table_name="framework_file_json_patches")
    op.drop_index("ix_framework_file_json_versions_package_id",
                  table_name="framework_file_json_versions")

    # 3. Drop tables in dependency order (leaves → root)
    op.drop_table("framework_file_json_tasks")
    op.drop_table("framework_file_json_patches")
    op.drop_table("framework_file_json_versions")
    op.drop_table("framework_file_json_packages")


def downgrade() -> None:
    """Re-create legacy tables for rollback safety (code is gone)."""

    # ── packages (root, no FK to other legacy tables) ────────────────
    op.create_table("framework_file_json_packages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("file_id", sa.Integer(), nullable=False,
                  comment="关联素材文件ID"),
        sa.Column("current_version_id", sa.Integer(), nullable=True),
        sa.Column("format_type", sa.String(length=32), nullable=False,
                  comment="格式类型: docx/xlsx/pptx/txt/csv"),
        sa.Column("package_status", sa.String(length=32), nullable=False,
                  comment="包状态: available/not_generated"),
        sa.Column("package_path", sa.String(length=512), nullable=False,
                  comment="包存储路径"),
        sa.Column("summary", sa.Text(), nullable=True, comment="摘要"),
        sa.Column("creator_id", sa.Integer(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False,
                  comment="Creation time"),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False,
                  comment="Last update time"),
        sa.ForeignKeyConstraint(["creator_id"],
                                ["framework_user_accounts.id"]),
        sa.ForeignKeyConstraint(["file_id"], ["framework_file_items.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── versions (depends on packages) ────────────────────────────────
    op.create_table("framework_file_json_versions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("package_id", sa.Integer(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False,
                  comment="版本号，自增"),
        sa.Column("json_content", sa.Text(), nullable=False,
                  comment="JSON内容全文"),
        sa.Column("summary", sa.Text(), nullable=True, comment="版本摘要"),
        sa.Column("creator_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False,
                  comment="Creation time"),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False,
                  comment="Last update time"),
        sa.ForeignKeyConstraint(["creator_id"],
                                ["framework_user_accounts.id"]),
        sa.ForeignKeyConstraint(["package_id"],
                                ["framework_file_json_packages.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── Circular FK back: packages → versions ─────────────────────────
    op.create_foreign_key(
        "fk_framework_file_json_packages_current_version",
        "framework_file_json_packages", "framework_file_json_versions",
        ["current_version_id"], ["id"],
    )

    # ── patches (depends on packages + versions) ──────────────────────
    op.create_table("framework_file_json_patches",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("package_id", sa.Integer(), nullable=False),
        sa.Column("source_version_id", sa.Integer(), nullable=False),
        sa.Column("target_version_id", sa.Integer(), nullable=False),
        sa.Column("operation_type", sa.String(length=64), nullable=False,
                  comment="操作类型: replace_text/modify_cell/insert_image"),
        sa.Column("json_path", sa.String(length=512), nullable=False,
                  comment="定位路径"),
        sa.Column("before_summary", sa.Text(), nullable=True,
                  comment="修改前摘要"),
        sa.Column("after_content", sa.Text(), nullable=False,
                  comment="修改后内容"),
        sa.Column("risk_level", sa.String(length=16), nullable=False,
                  comment="风险等级: low/medium/high"),
        sa.Column("reason", sa.Text(), nullable=True, comment="修改原因"),
        sa.Column("patch_status", sa.String(length=32), nullable=False,
                  comment="补丁状态: applied/pending_review/rejected"),
        sa.Column("creator_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False,
                  comment="Creation time"),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False,
                  comment="Last update time"),
        sa.ForeignKeyConstraint(["creator_id"],
                                ["framework_user_accounts.id"]),
        sa.ForeignKeyConstraint(["package_id"],
                                ["framework_file_json_packages.id"]),
        sa.ForeignKeyConstraint(["source_version_id"],
                                ["framework_file_json_versions.id"]),
        sa.ForeignKeyConstraint(["target_version_id"],
                                ["framework_file_json_versions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── tasks (depends on packages) ───────────────────────────────────
    op.create_table("framework_file_json_tasks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("file_id", sa.Integer(), nullable=False),
        sa.Column("package_id", sa.Integer(), nullable=True),
        sa.Column("task_type", sa.String(length=64), nullable=False,
                  comment="任务类型"),
        sa.Column("status", sa.String(length=32), nullable=False,
                  comment="任务状态"),
        sa.Column("progress", sa.SmallInteger(), nullable=False,
                  comment="进度 0-100"),
        sa.Column("error_message", sa.Text(), nullable=True,
                  comment="错误信息"),
        sa.Column("creator_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False,
                  comment="Creation time"),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False,
                  comment="Last update time"),
        sa.ForeignKeyConstraint(["creator_id"],
                                ["framework_user_accounts.id"]),
        sa.ForeignKeyConstraint(["file_id"], ["framework_file_items.id"]),
        sa.ForeignKeyConstraint(["package_id"],
                                ["framework_file_json_packages.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── Re-create the indexes from migration 3b8f6e1a2c4d ────────────
    op.create_index("ix_framework_file_json_versions_package_id",
                    "framework_file_json_versions", ["package_id"])
    op.create_index("ix_framework_file_json_patches_package_id",
                    "framework_file_json_patches", ["package_id"])
