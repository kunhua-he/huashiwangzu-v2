"""Remove the retired Agent workflow recipe execution path.

Revision ID: 5d9e0f1a2b3c
Revises: 4c8d9e0f1a2b
Create Date: 2026-07-13 13:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "5d9e0f1a2b3c"
down_revision: Union[str, Sequence[str], None] = "4c8d9e0f1a2b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(sa.text(
        "UPDATE framework_system_task_queues "
        "SET status = 'failed', completed_at = NOW(), "
        "    error_message = 'Retired workflow recipe mining task' "
        "WHERE task_type = 'workflow_mine' AND status IN ('pending', 'running')"
    ))
    op.execute(sa.text("DROP TABLE IF EXISTS agent_workflow_recipes"))


def downgrade() -> None:
    op.create_table(
        "agent_workflow_recipes",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False, server_default=""),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("intent_label", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("trigger_condition", sa.Text(), nullable=False, server_default=""),
        sa.Column("steps", sa.JSON(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("tools_used", sa.JSON(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="proposal"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("success_weight", sa.Float(), nullable=False, server_default="0"),
        sa.Column("fail_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("avg_duration_ms", sa.Float(), nullable=True),
        sa.Column("avg_tool_count", sa.Float(), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("source_conversation_id", sa.BigInteger(), nullable=True),
        sa.Column("source_trajectory_id", sa.BigInteger(), nullable=True),
        sa.Column("source_experience_id", sa.BigInteger(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_workflow_recipes_owner", "agent_workflow_recipes", ["owner_id"])
