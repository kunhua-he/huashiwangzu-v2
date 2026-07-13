"""Regression tests for structured Agent action failures."""
from __future__ import annotations

import json

import pytest

from .runtime import action_plan_validator, tool_loop_runtime
from .runtime.action_plan import ActionPlan
from .runtime.action_planner import ActionPlanningResult, PlannerDecisionType
from .runtime.runtime_policy import RuntimePolicy
from .runtime.tool_failure_normalizer import (
    effective_tool_name,
    normalize_tool_result_for_model,
)
from .runtime.tool_loop_runtime import ToolLoopRuntime


def test_normalize_external_success_false_as_hard_failure() -> None:
    result, signal = normalize_tool_result_for_model(
        {"success": False, "error": "Connection refused"},
        "web-tools__fetch",
    )

    assert isinstance(result, dict)
    assert result["success"] is False
    assert result["error_class"] == "network_error"
    assert result["failure_kind"] == "hard"
    assert result["hard_failure"] is True
    assert result["tool_failure"]["tool_name"] == "web-tools__fetch"
    assert "Do not treat it as successful" in result["model_instruction"]
    assert signal == result["tool_failure"]


def test_normalize_nested_timeout_preserves_transport_success() -> None:
    result, signal = normalize_tool_result_for_model(
        {
            "success": True,
            "data": {
                "success": False,
                "error": "timed out while opening page",
            },
        },
        "browser-tools__open",
    )

    assert isinstance(result, dict)
    assert result["success"] is False
    assert result["transport_success"] is True
    assert result["error"] == "timed out while opening page"
    assert result["error_class"] == "timeout"
    assert result["hard_failure"] is True
    assert signal is not None
    assert signal["source"] == "data"


def test_effective_tool_name_is_the_direct_capability_name() -> None:
    assert effective_tool_name({"name": "web-tools__fetch", "args": {}}) == "web-tools__fetch"


class _DummySession:
    async def __aenter__(self) -> "_DummySession":
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None

    async def execute(self, *args: object, **kwargs: object) -> None:
        raise RuntimeError("skip database in unit test")


class _FakeSink:
    workflow_link = None
    workflow_run_id = None
    workflow_step_id = None
    agent_run_id = None
    user_input = "run capability"

    async def record_failure(self, *args: object, **kwargs: object) -> None:
        return None

    async def persist_assistant(self, *args: object, **kwargs: object) -> int:
        return 123

    async def persist_pending_events(self, *args: object, **kwargs: object) -> int:
        return 1

    async def generate_completion_evidence(self, *args: object, **kwargs: object) -> list[dict]:
        return []

    def check_tool_success(self, tool_events: list[dict]) -> bool:
        return False

    async def record_trajectory(self, *args: object, **kwargs: object) -> dict:
        return {"recorded": False}

    async def run_post_turn_hooks(self, *args: object, **kwargs: object) -> None:
        return None

    async def workflow_record_tool_started(self, *args: object, **kwargs: object) -> None:
        return None

    async def workflow_mark_tool_result(self, *args: object, **kwargs: object) -> None:
        return None

    async def workflow_record_runtime_failure(self, *args: object, **kwargs: object) -> None:
        return None

    async def workflow_complete_turn(self, *args: object, **kwargs: object) -> None:
        return None

    async def submit_completed_experience(self, *args: object, **kwargs: object) -> dict:
        return {"submitted": False}


class _Planner:
    def __init__(self, plan: ActionPlan) -> None:
        self.plan = plan

    async def decide(self, **kwargs: object) -> ActionPlanningResult:
        return ActionPlanningResult(
            decision=PlannerDecisionType.ACTION_GRAPH,
            plan=self.plan,
        )


def _catalog(*, timeout_seconds: float = 1) -> dict:
    return {
        "catalog_hash": "a" * 64,
        "principal": {"profile_version": "b" * 16},
        "candidates": [{
            "capability_id": 1,
            "module": "web-tools",
            "action": "fetch",
            "parameters": {"url": {"type": "string"}},
            "execution_contract": {
                "side_effect_level": "none",
                "timeout_seconds": timeout_seconds,
            },
        }],
    }


def _plan() -> ActionPlan:
    return ActionPlan.model_validate({
        "goal": "Fetch the page",
        "catalog_hash": "a" * 64,
        "principal_version": "b" * 16,
        "actions": [{
            "id": "fetch",
            "capability_id": 1,
            "capability": "web-tools__fetch",
            "arguments": {"url": "https://example.invalid"},
            "completion_check": "Fetch completes",
        }],
        "final_completion_check": "Fetch completes",
    })


def _decode_sse(event: object) -> dict | None:
    if not isinstance(event, bytes):
        return None
    value = event.decode("utf-8")
    if not value.startswith("data: ") or value.startswith("data: [DONE]"):
        return None
    return json.loads(value[6:].strip())


async def _allow_snapshot(**kwargs: object) -> dict:
    return {}


async def _allow_policy(*args: object, **kwargs: object) -> dict:
    return {"allowed": True}


@pytest.mark.asyncio
async def test_runtime_emits_failed_observation_without_retrying(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services import module_registry

    calls = 0

    async def fail_capability(*args: object, **kwargs: object) -> dict:
        nonlocal calls
        calls += 1
        return {"success": False, "error": "Connection refused"}

    monkeypatch.setattr(tool_loop_runtime, "AsyncSessionLocal", lambda: _DummySession())
    monkeypatch.setattr(tool_loop_runtime, "check_action_allowed", _allow_policy)
    monkeypatch.setattr(action_plan_validator, "validate_execution_snapshot", _allow_snapshot)
    monkeypatch.setattr(module_registry, "call_capability", fail_capability)
    runtime = ToolLoopRuntime(
        conversation_id=1,
        owner_id=1,
        policy=RuntimePolicy(max_tool_rounds=1, enable_checkpointer=False),
        capability_catalog=_catalog(),
        planner=_Planner(_plan()),  # type: ignore[arg-type]
    )

    events = [
        event
        async for event in runtime.run(
            [{"role": "user", "content": "fetch"}],
            _FakeSink(),  # type: ignore[arg-type]
        )
    ]
    decoded = [_decode_sse(event) for event in events]

    assert calls == 1
    assert any(
        item
        and item.get("type") == "tool_result"
        and item.get("status") == "failed"
        for item in decoded
    )


@pytest.mark.asyncio
async def test_runtime_uses_capability_contract_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services import module_registry

    async def slow_capability(*args: object, **kwargs: object) -> dict:
        await tool_loop_runtime.asyncio.sleep(0.05)
        return {"success": True}

    monkeypatch.setattr(tool_loop_runtime, "AsyncSessionLocal", lambda: _DummySession())
    monkeypatch.setattr(tool_loop_runtime, "check_action_allowed", _allow_policy)
    monkeypatch.setattr(action_plan_validator, "validate_execution_snapshot", _allow_snapshot)
    monkeypatch.setattr(module_registry, "call_capability", slow_capability)
    runtime = ToolLoopRuntime(
        conversation_id=1,
        owner_id=1,
        policy=RuntimePolicy(max_tool_rounds=1, enable_checkpointer=False),
        capability_catalog=_catalog(timeout_seconds=0.01),
        planner=_Planner(_plan()),  # type: ignore[arg-type]
    )

    events = [
        event
        async for event in runtime.run(
            [{"role": "user", "content": "fetch"}],
            _FakeSink(),  # type: ignore[arg-type]
        )
    ]
    decoded = [_decode_sse(event) for event in events]

    assert any(
        item
        and item.get("type") == "tool_result"
        and item.get("error_class") == "timeout"
        for item in decoded
    )
