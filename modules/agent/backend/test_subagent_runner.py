"""Regression tests for subagent runner ownership context."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@pytest.mark.asyncio
async def test_subagent_executes_exposed_direct_read_capability(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services import module_registry

    from modules.agent.backend.runtime import action_plan_validator
    from modules.agent.backend.runtime.action_plan import ActionPlan
    from modules.agent.backend.runtime.action_planner import (
        ActionPlanningResult,
        PlannerDecisionType,
    )
    from modules.agent.backend.services import subagent_runner

    captured_calls: list[dict] = []

    class Planner:
        async def decide(self, **kwargs: object) -> ActionPlanningResult:
            return ActionPlanningResult(
                decision=PlannerDecisionType.ACTION_GRAPH,
                plan=ActionPlan.model_validate({
                    "goal": "search knowledge",
                    "catalog_hash": "a" * 64,
                    "principal_version": "b" * 16,
                    "actions": [{
                        "id": "search",
                        "capability_id": 1,
                        "capability": "knowledge__search",
                        "arguments": {"query": "agent"},
                        "completion_check": "Search completes",
                    }],
                    "final_completion_check": "Search completes",
                }),
            )

    async def fake_call_capability(
        module: str,
        action: str,
        params: dict,
        **kwargs: object,
    ) -> dict:
        captured_calls.append({"module": module, "action": action, "params": params, **kwargs})
        return {"success": True, "data": {"results": []}}

    async def fake_catalog(**kwargs: object) -> dict:
        return {
            "catalog_hash": "a" * 64,
            "principal": {"profile_version": "b" * 16},
            "candidates": [{
                "capability_id": 1,
                "module": "knowledge",
                "action": "search",
                "parameters": {"query": {"type": "string"}},
                "execution_contract": {"side_effect_level": "none"},
            }],
        }

    async def validate_snapshot(**kwargs: object) -> dict:
        return {}

    async def system_prompt(*args: object, **kwargs: object) -> str:
        return "test"

    monkeypatch.setattr(subagent_runner, "retrieve_capabilities", fake_catalog)
    monkeypatch.setattr(subagent_runner, "_build_system_prompt", system_prompt)
    monkeypatch.setattr(action_plan_validator, "validate_execution_snapshot", validate_snapshot)
    monkeypatch.setattr(
        module_registry,
        "call_capability",
        fake_call_capability,
    )

    result = await subagent_runner.run_single_task(
        task_desc="search knowledge",
        max_rounds=2,
        task_write_enabled=False,
        caller="user:55",
        caller_role="viewer",
        owner_id=55,
        planner=Planner(),  # type: ignore[arg-type]
    )

    assert result["status"] == "completed"
    assert captured_calls[0]["module"] == "knowledge"
    assert captured_calls[0]["action"] == "search"
    assert captured_calls[0]["caller"] == "user:55"
    assert result["tool_calls"][0]["name"] == "knowledge__search"


@pytest.mark.asyncio
async def test_subagent_write_guard_blocks_direct_write_capability(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from modules.agent.backend.runtime.action_planner import (
        ActionPlanningResult,
        PlannerDecisionType,
    )
    from modules.agent.backend.services import subagent_runner

    class Planner:
        async def decide(self, **kwargs: object) -> ActionPlanningResult:
            assert not kwargs["catalog"]["candidates"]  # type: ignore[index]
            return ActionPlanningResult(
                decision=PlannerDecisionType.DIRECT_ANSWER,
                answer="Write access is disabled.",
            )

    async def fake_catalog(**kwargs: object) -> dict:
        return {
            "catalog_hash": "a" * 64,
            "principal": {"profile_version": "b" * 16},
            "candidates": [{
                "capability_id": 2,
                "module": "agent",
                "action": "update_my_profile",
                "execution_contract": {"side_effect_level": "update"},
            }],
        }

    async def system_prompt(*args: object, **kwargs: object) -> str:
        return "test"

    monkeypatch.setattr(subagent_runner, "retrieve_capabilities", fake_catalog)
    monkeypatch.setattr(subagent_runner, "_build_system_prompt", system_prompt)
    result = await subagent_runner.run_single_task(
        task_desc="try to update profile",
        max_rounds=1,
        task_write_enabled=False,
        caller="user:55",
        caller_role="viewer",
        owner_id=55,
        planner=Planner(),  # type: ignore[arg-type]
    )

    assert result["status"] == "completed"
    assert result["tool_calls"] == []
    assert result["conclusion"] == "Write access is disabled."


@pytest.mark.asyncio
async def test_subagent_rejects_tool_outside_authorized_catalog(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from modules.agent.backend.runtime.action_planner import (
        ActionPlanningResult,
        PlannerDecisionType,
    )
    from modules.agent.backend.services import subagent_runner

    class Planner:
        async def decide(self, **kwargs: object) -> ActionPlanningResult:
            assert not kwargs["catalog"]["candidates"]  # type: ignore[index]
            return ActionPlanningResult(
                decision=PlannerDecisionType.DIRECT_ANSWER,
                answer="No authorized capability is available.",
            )

    async def fake_catalog(**kwargs: object) -> dict:
        return {
            "catalog_hash": "a" * 64,
            "principal": {"profile_version": "b" * 16},
            "candidates": [{
                "capability_id": 1,
                "module": "knowledge",
                "action": "search",
                "execution_contract": {"side_effect_level": "none"},
            }],
        }

    async def system_prompt(*args: object, **kwargs: object) -> str:
        return "test"

    monkeypatch.setattr(subagent_runner, "retrieve_capabilities", fake_catalog)
    monkeypatch.setattr(subagent_runner, "_build_system_prompt", system_prompt)
    result = await subagent_runner.run_single_task(
        task_desc="search knowledge",
        base_tools=[],
        max_rounds=2,
        task_write_enabled=False,
        caller="user:55",
        caller_role="viewer",
        owner_id=55,
        planner=Planner(),  # type: ignore[arg-type]
    )

    assert result["status"] == "completed"
    assert result["conclusion"] == "No authorized capability is available."
    assert result["tool_results"] == []


@pytest.mark.asyncio
async def test_spawn_subagent_track_trajectory_persists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app import database

    from modules.agent.backend.handlers import tool as tool_handler
    from modules.agent.backend.services import (
        subagent_runner,
        trajectory_service,
    )

    class DummySession:
        async def __aenter__(self) -> object:
            return object()

        async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
            return None

    async def fake_run_single_task(**kwargs: object) -> dict:
        return {
            "task": kwargs["task_desc"],
            "status": "completed",
            "error": None,
            "conclusion": "subagent done",
            "rounds_used": 1,
            "tool_calls": [{"name": "skill_list", "arguments": {}}],
            "tool_results": [{"name": "skill_list", "result": {"skills": []}}],
        }

    captured: dict[str, object] = {}

    async def fake_record_turn(db: object, **kwargs: object) -> dict:
        captured.update(kwargs)
        return {"id": 123, "turn_index": kwargs["turn_index"], "recorded": True}

    monkeypatch.setattr(database, "AsyncSessionLocal", lambda: DummySession())
    monkeypatch.setattr(subagent_runner, "run_single_task", fake_run_single_task)
    monkeypatch.setattr(trajectory_service, "record_turn", fake_record_turn)

    result = await tool_handler._cap_spawn_subagent(
        {
            "task": "inspect data",
            "track_trajectory": True,
            "conversation_id": 777,
            "session_id": "subagent-test",
            "turn_index_offset": 0,
        },
        caller="user:55",
    )

    assert result["completed"] == 1
    assert result["trajectory"][0]["recorded"] is True
    assert result["trajectory"][0]["id"] == 123
    assert captured["conversation_id"] == 777
    assert captured["owner_id"] == 55
    assert captured["session_id"] == "subagent-test"
    assert captured["tool_calls"] == [{"name": "skill_list", "arguments": {}}]
    assert captured["assistant_response"] == "subagent done"
