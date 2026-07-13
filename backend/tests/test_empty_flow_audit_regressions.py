import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@pytest.mark.asyncio
async def test_skill_usage_stats_consumes_execute_rows_once() -> None:
    from modules.agent.backend.services import skill_governance_service as sgs

    class FakeRows:
        def __init__(self) -> None:
            self.calls = 0

        def fetchall(self) -> list[tuple]:
            self.calls += 1
            if self.calls > 1:
                return []
            return [("memory__recall", 2, 1, 12.5, 1)]

    class FakeDb:
        def __init__(self) -> None:
            self.rows = FakeRows()

        async def execute(self, _stmt, _params) -> FakeRows:
            return self.rows

    db = FakeDb()
    stats = await sgs.get_skill_usage_stats(db, days=7)

    assert db.rows.calls == 1
    assert stats == [
        {
            "skill_name": "memory__recall",
            "total_calls": 2,
            "success_count": 1,
            "avg_duration_ms": 12.5,
            "error_count": 1,
            "error_rate": 0.5,
        }
    ]


@pytest.mark.asyncio
async def test_direct_capability_records_invocation_usage(monkeypatch: pytest.MonkeyPatch) -> None:
    from app import database

    from modules.agent.backend.services import capability_execution
    from modules.agent.backend.services import skill_governance_service as sgs

    recorded: list[dict] = []

    async def fake_record_skill_usage(db, **kwargs) -> None:
        recorded.append(kwargs)

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

    monkeypatch.setattr(database, "AsyncSessionLocal", lambda: FakeSession())
    monkeypatch.setattr(sgs, "record_skill_usage", fake_record_skill_usage)

    await capability_execution.record_capability_invocation(
        "memory__recall",
        success=True,
        duration_ms=12.0,
        caller="user:42",
    )

    assert len(recorded) == 1
    assert recorded[0]["skill_name"] == "memory__recall"
    assert recorded[0]["success"] is True
    assert recorded[0]["owner_id"] == 42
    assert recorded[0]["conversation_id"] is None


def test_imagegen_failure_path_raises_after_recording_failed_history() -> None:
    router_src = (REPO_ROOT / "modules" / "image-gen" / "backend" / "router.py").read_text("utf-8")

    assert 'status="failed"' in router_src
    assert "raise ValidationError(friendly) from e" in router_src
    assert "raise ValidationError(\"生图异常，请稍后重试\") from e" in router_src
    assert "image generation produced no downloadable images" in router_src
    assert "raise ValidationError(\"生图失败：未生成可用图片\")" in router_src
    assert 'return {"images": [], "placeholder": False, "error": friendly' not in router_src
    assert 'return {"images": [], "placeholder": False, "error": "生图异常，请稍后重试"' not in router_src
    assert 'return {"records": []}' not in router_src


def test_memory_experience_manifest_matches_runtime_capability_contract() -> None:
    manifest = json.loads((REPO_ROOT / "modules" / "memory" / "manifest.json").read_text("utf-8"))
    actions = {item["action"]: item for item in manifest["public_actions"]}

    save_params = actions["save_experience"]["parameters"]
    assert {"trigger_condition", "steps", "tools_used", "source_conversation_id", "scope"}.issubset(save_params)

    match_params = actions["match_experience"]["parameters"]
    assert "query" in match_params
    assert "trigger_condition" not in match_params
