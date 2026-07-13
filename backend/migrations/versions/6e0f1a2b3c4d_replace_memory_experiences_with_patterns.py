"""Replace legacy memory experiences with structured ExperiencePattern.

Revision ID: 6e0f1a2b3c4d
Revises: 5d9e0f1a2b3c
Create Date: 2026-07-13 13:30:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "6e0f1a2b3c4d"
down_revision: Union[str, Sequence[str], None] = "5d9e0f1a2b3c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_LEGACY_COLUMNS = {
    "owner_id",
    "scope",
    "trigger_condition",
    "trigger_embedding",
    "steps",
    "tools_used",
    "success_weight",
    "fail_count",
    "fail_notes",
    "active",
}


def _columns() -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {item["name"] for item in inspector.get_columns("memory_experiences")}


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "memory_experiences" not in inspector.get_table_names():
        raise RuntimeError("memory_experiences must exist before ExperiencePattern migration")
    columns = _columns()

    additions = {
        "scope_type": sa.Column("scope_type", sa.String(32), nullable=True, server_default="user"),
        "scope_id": sa.Column("scope_id", sa.BigInteger(), nullable=True),
        "goal_signature": sa.Column("goal_signature", sa.Text(), nullable=True, server_default=""),
        "goal_embedding": sa.Column("goal_embedding", Vector(1024), nullable=True),
        "preconditions": sa.Column("preconditions", postgresql.JSONB(), nullable=True, server_default=sa.text("'{}'::jsonb")),
        "action_pattern": sa.Column("action_pattern", postgresql.JSONB(), nullable=True, server_default=sa.text("'[]'::jsonb")),
        "completion_evidence": sa.Column("completion_evidence", postgresql.JSONB(), nullable=True, server_default=sa.text("'{}'::jsonb")),
        "capability_ids": sa.Column("capability_ids", postgresql.ARRAY(sa.Integer()), nullable=True, server_default=sa.text("'{}'::integer[]")),
        "capability_contract_hashes": sa.Column("capability_contract_hashes", postgresql.JSONB(), nullable=True, server_default=sa.text("'{}'::jsonb")),
        "success_count": sa.Column("success_count", sa.Integer(), nullable=True, server_default="1"),
        "distinct_user_count": sa.Column("distinct_user_count", sa.Integer(), nullable=True, server_default="1"),
        "failure_count": sa.Column("failure_count", sa.Integer(), nullable=True, server_default="0"),
        "failure_notes": sa.Column("failure_notes", postgresql.JSONB(), nullable=True, server_default=sa.text("'[]'::jsonb")),
        "created_by_user_id": sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        "contributor_user_ids": sa.Column("contributor_user_ids", postgresql.ARRAY(sa.Integer()), nullable=True, server_default=sa.text("'{}'::integer[]")),
        "contributor_department_ids": sa.Column("contributor_department_ids", postgresql.ARRAY(sa.Integer()), nullable=True, server_default=sa.text("'{}'::integer[]")),
        "confidence": sa.Column("confidence", sa.Float(), nullable=True, server_default="0.5"),
        "last_verified_at": sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        "status": sa.Column("status", sa.String(32), nullable=True, server_default="candidate"),
        "risk_level": sa.Column("risk_level", sa.String(32), nullable=True, server_default="none"),
        "privacy_status": sa.Column("privacy_status", sa.String(32), nullable=True, server_default="sanitized"),
        "requires_review": sa.Column("requires_review", sa.Boolean(), nullable=True, server_default=sa.false()),
        "reviewed_by": sa.Column("reviewed_by", sa.Integer(), nullable=True),
        "reviewed_at": sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        "review_note": sa.Column("review_note", sa.Text(), nullable=True),
    }
    for name, column in additions.items():
        if name not in columns:
            op.add_column("memory_experiences", column)

    columns = _columns()
    if "trigger_condition" in columns:
        op.execute(sa.text("""
            UPDATE memory_experiences
            SET scope_type = CASE
                    WHEN scope = 'team' THEN 'department'
                    WHEN scope IN ('global', 'user') THEN scope
                    ELSE 'user'
                END,
                scope_id = CASE WHEN scope = 'global' THEN NULL ELSE owner_id END,
                goal_signature = COALESCE(trigger_condition, ''),
                success_count = COALESCE(success_weight, 1),
                failure_count = COALESCE(fail_count, 0),
                created_by_user_id = owner_id,
                contributor_user_ids = CASE
                    WHEN owner_id IS NULL THEN '{}'::integer[]
                    ELSE ARRAY[owner_id]
                END,
                distinct_user_count = CASE WHEN owner_id IS NULL THEN 0 ELSE 1 END,
                status = 'suspended',
                privacy_status = 'legacy_unreviewed',
                requires_review = true
        """))

    op.execute(sa.text("""
        UPDATE memory_experiences
        SET scope_type = COALESCE(scope_type, 'user'),
            goal_signature = COALESCE(goal_signature, ''),
            preconditions = COALESCE(preconditions, '{}'::jsonb),
            action_pattern = COALESCE(action_pattern, '[]'::jsonb),
            completion_evidence = COALESCE(completion_evidence, '{}'::jsonb),
            capability_ids = COALESCE(capability_ids, '{}'::integer[]),
            capability_contract_hashes = COALESCE(capability_contract_hashes, '{}'::jsonb),
            success_count = COALESCE(success_count, 1),
            distinct_user_count = COALESCE(distinct_user_count, 1),
            failure_count = COALESCE(failure_count, 0),
            failure_notes = COALESCE(failure_notes, '[]'::jsonb),
            contributor_user_ids = COALESCE(contributor_user_ids, '{}'::integer[]),
            contributor_department_ids = COALESCE(contributor_department_ids, '{}'::integer[]),
            confidence = COALESCE(confidence, 0.5),
            status = COALESCE(status, 'candidate'),
            risk_level = COALESCE(risk_level, 'none'),
            privacy_status = COALESCE(privacy_status, 'sanitized'),
            requires_review = COALESCE(requires_review, false)
    """))

    for column_name in (
        "scope_type",
        "goal_signature",
        "preconditions",
        "action_pattern",
        "completion_evidence",
        "capability_ids",
        "capability_contract_hashes",
        "success_count",
        "distinct_user_count",
        "failure_count",
        "failure_notes",
        "contributor_user_ids",
        "contributor_department_ids",
        "confidence",
        "status",
        "risk_level",
        "privacy_status",
        "requires_review",
    ):
        op.alter_column("memory_experiences", column_name, nullable=False)

    for index_name in (
        "ux_memory_experiences_active_scope_content",
        "ix_memory_experiences_scope_owner",
        "ix_memory_experiences_trigger_embedding",
    ):
        op.execute(sa.text(f'DROP INDEX IF EXISTS "{index_name}"'))
    for column_name in sorted(_LEGACY_COLUMNS & _columns()):
        op.drop_column("memory_experiences", column_name)

    op.execute(sa.text("""
        CREATE INDEX IF NOT EXISTS ix_memory_experiences_pattern_scope
        ON memory_experiences (scope_type, scope_id, status)
    """))
    op.execute(sa.text("""
        CREATE INDEX IF NOT EXISTS ix_memory_experiences_capability_ids
        ON memory_experiences USING GIN (capability_ids)
    """))
    op.execute(sa.text("""
        CREATE UNIQUE INDEX IF NOT EXISTS ux_memory_experiences_scope_pattern
        ON memory_experiences (
            scope_type,
            COALESCE(scope_id, 0),
            md5(goal_signature),
            md5(action_pattern::text)
        )
        WHERE status NOT IN ('rejected', 'suspended')
    """))
    op.execute(sa.text("""
        CREATE INDEX IF NOT EXISTS ix_memory_experiences_goal_embedding
        ON memory_experiences USING ivfflat
        (goal_embedding vector_cosine_ops) WITH (lists = 100)
    """))


def downgrade() -> None:
    raise RuntimeError("ExperiencePattern migration is intentionally forward-only")
