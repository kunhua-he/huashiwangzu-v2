"""Regression checks for memory experience ownership/scope boundaries.

These are source-level checks so they do not touch live memory data or the
embedding service. The live behavior is covered by module capability tests.
"""

from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
MEMORY_BACKEND = BACKEND_ROOT.parent / "modules" / "memory" / "backend"
MODELS_SRC = (MEMORY_BACKEND / "models.py").read_text("utf-8")
INIT_SRC = (MEMORY_BACKEND / "init_db.py").read_text("utf-8")
CAP_SRC = (MEMORY_BACKEND / "services" / "capabilities.py").read_text("utf-8")
EXP_SRC = (MEMORY_BACKEND / "services" / "experience_service.py").read_text("utf-8")
MEMORY_SERVICE_SRC = (MEMORY_BACKEND / "services" / "memory_service.py").read_text("utf-8")


def test_experience_model_has_owner_and_scope() -> None:
    assert "owner_id: Mapped[int | None]" in MODELS_SRC
    assert "scope: Mapped[str]" in MODELS_SRC
    assert "server_default=sa_text(\"'user'\")" in MODELS_SRC


def test_existing_experiences_are_migrated_to_global_before_user_default() -> None:
    assert "ADD COLUMN IF NOT EXISTS owner_id INTEGER" in INIT_SRC
    assert "ADD COLUMN IF NOT EXISTS scope VARCHAR(16)" in INIT_SRC
    assert "UPDATE memory_experiences SET scope = 'global' WHERE scope IS NULL" in INIT_SRC
    assert "ALTER TABLE memory_experiences ALTER COLUMN scope SET DEFAULT 'user'" in INIT_SRC


def test_user_callers_cannot_write_global_experiences() -> None:
    assert "全局经验只能由系统 curated 通路写入" in EXP_SRC
    assert "if scope == EXPERIENCE_SCOPE_GLOBAL" in EXP_SRC
    assert "if not _is_system_caller(caller)" in EXP_SRC
    assert "_resolve_experience_write_scope(" in CAP_SRC


def test_match_experience_prefers_user_team_then_global() -> None:
    assert "COALESCE(scope, 'global') = 'global'" in EXP_SRC
    assert "scope = 'user' AND owner_id = :owner_id" in EXP_SRC
    assert "scope = 'team' AND owner_id = ANY" in EXP_SRC
    assert "WHEN 'user' THEN 0" in EXP_SRC
    assert "WHEN 'team' THEN 1" in EXP_SRC
    assert "ORDER BY scope_rank ASC" in EXP_SRC


def test_feedback_counts_are_atomic_and_scope_checked() -> None:
    assert "UPDATE memory_experiences" in EXP_SRC
    assert "RETURNING id, success_weight, fail_count" in EXP_SRC
    assert "COALESCE(success_weight, 1) + 1" in EXP_SRC
    assert "COALESCE(fail_count, 0) + 1" in EXP_SRC
    assert "只能反馈自己或可见范围内的经验" in EXP_SRC


def test_dream_and_links_have_duplicate_guards() -> None:
    assert "ux_memory_links_owner_pair_relation" in INIT_SRC
    assert "ON CONFLICT DO NOTHING" in MEMORY_SERVICE_SRC
    assert "ux_memory_experiences_active_scope_content" in INIT_SRC
    assert "_do_experience_dream(db, owner_id if owner_id else None, exp_scope)" in CAP_SRC
