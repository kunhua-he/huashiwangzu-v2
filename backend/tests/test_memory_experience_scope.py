"""Source contract checks for the memory-owned ExperiencePattern projection."""

from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
MEMORY_BACKEND = BACKEND_ROOT.parent / "modules" / "memory" / "backend"
MIGRATION_SRC = (
    BACKEND_ROOT
    / "migrations"
    / "versions"
    / "6e0f1a2b3c4d_replace_memory_experiences_with_patterns.py"
).read_text("utf-8")
MODELS_SRC = (MEMORY_BACKEND / "models.py").read_text("utf-8")
INIT_SRC = (MEMORY_BACKEND / "init_db.py").read_text("utf-8")
CAP_SRC = (MEMORY_BACKEND / "services" / "capabilities.py").read_text("utf-8")
EXP_SRC = (MEMORY_BACKEND / "services" / "experience_service.py").read_text("utf-8")


def test_experience_model_has_single_structured_contract() -> None:
    for field in (
        "scope_type", "scope_id", "goal_signature", "preconditions",
        "action_pattern", "completion_evidence", "capability_ids",
        "capability_contract_hashes", "success_count", "distinct_user_count",
        "failure_count", "confidence", "status", "risk_level",
    ):
        assert f"{field}: Mapped" in MODELS_SRC
    for legacy in (
        "owner_id: Mapped[int | None]", "scope: Mapped[str]",
        "trigger_condition: Mapped[str]", "steps: Mapped[str]",
        "tools_used: Mapped[str]", "success_weight: Mapped[int]",
    ):
        assert legacy not in MODELS_SRC


def test_forward_migration_removes_legacy_experience_columns() -> None:
    for column in (
        "owner_id", "scope", "trigger_condition", "trigger_embedding", "steps",
        "tools_used", "success_weight", "fail_count", "fail_notes", "active",
    ):
        assert f"DROP COLUMN IF EXISTS {column}" in INIT_SRC
    assert "ux_memory_experiences_scope_pattern" in INIT_SRC
    assert "ix_memory_experiences_goal_embedding" in INIT_SRC


def test_alembic_migration_uses_native_pgvector_contract() -> None:
    assert "from pgvector.sqlalchemy import Vector" in MIGRATION_SRC
    assert '"goal_embedding": sa.Column("goal_embedding", Vector(1024)' in MIGRATION_SRC
    assert '"goal_embedding", postgresql.ARRAY(sa.Float())' not in MIGRATION_SRC
    assert "ix_memory_experiences_goal_embedding" in MIGRATION_SRC


def test_all_six_scopes_are_principal_filtered_before_recall() -> None:
    for scope in (
        "global", "organization", "department", "position", "user", "conversation",
    ):
        assert f'EXPERIENCE_SCOPE_{scope.upper()} = "{scope}"' in EXP_SRC
    assert "_visibility_condition(scopes)" in EXP_SRC
    assert "principal_context" in CAP_SRC
    assert "resolve_principal_context" in CAP_SRC


def test_contract_and_permission_snapshot_filter_before_return() -> None:
    assert "authorized_capability_snapshot" in CAP_SRC
    assert "MemoryExperience.capability_ids.contained_by(authorized_ids)" in EXP_SRC
    assert "_contracts_current(exp, current_contracts)" in EXP_SRC
    assert "经验包含当前 principal 未授权或不存在的 capability" in EXP_SRC


def test_feedback_is_scope_checked_and_failure_can_suspend() -> None:
    assert "MemoryExperience.id == experience_id, _visibility_condition(scopes)" in EXP_SRC
    assert ".with_for_update()" in EXP_SRC
    assert "exp.failure_count = int(exp.failure_count or 0) + 1" in EXP_SRC
    assert 'return "suspended", False' in EXP_SRC


def test_shared_promotion_is_sanitized_and_high_risk_reviewed() -> None:
    assert 'exp.privacy_status != "sanitized"' in EXP_SRC
    assert 'return "review_pending", True' in EXP_SRC
    assert "GLOBAL_MIN_DEPARTMENTS" in EXP_SRC
    assert "_cap_review_experience" in CAP_SRC
