from __future__ import annotations

import asyncio

import pytest

from modules.agent.backend.runtime.action_graph_executor import (
    ActionGraphExecutor,
    ActionGraphStatus,
)
from modules.agent.backend.runtime.action_plan import ActionPlan, ActionPlanCheckpoint
from modules.agent.backend.runtime.action_plan_validator import ActionPlanValidator


def _catalog() -> dict:
    return {
        "catalog_hash": "a" * 64,
        "principal": {"profile_version": "b" * 20},
        "candidates": [
            {
                "capability_id": 1,
                "module": "demo",
                "action": "find",
                "parameters": {"query": {"type": "string"}},
                "execution_contract": {
                    "side_effect_level": "none",
                    "parallel_safe": True,
                    "timeout_seconds": 1,
                    "output_reference_types": ["file"],
                },
            },
            {
                "capability_id": 2,
                "module": "demo",
                "action": "open",
                "parameters": {"file_id": {"type": "integer"}},
                "execution_contract": {
                    "side_effect_level": "none",
                    "parallel_safe": True,
                    "timeout_seconds": 1,
                },
            },
            {
                "capability_id": 3,
                "module": "demo",
                "action": "write",
                "parameters": {},
                "execution_contract": {
                    "side_effect_level": "create",
                    "parallel_safe": False,
                    "timeout_seconds": 1,
                },
            },
        ],
    }


def _plan(actions: list[dict]) -> ActionPlan:
    return ActionPlan.model_validate({
        "goal": "Execute a verified graph",
        "catalog_hash": "a" * 64,
        "principal_version": "b" * 20,
        "actions": actions,
        "final_completion_check": "All required actions complete",
    })


class OfflineValidator(ActionPlanValidator):
    async def validate_before_execution(self, action):
        return self._candidates[action.capability]


@pytest.mark.asyncio
async def test_executor_runs_ready_dependencies_and_binds_resource_reference() -> None:
    plan = _plan([
        {
            "id": "find",
            "capability_id": 1,
            "capability": "demo__find",
            "arguments": {"query": "report"},
            "expected_references": ["file"],
            "completion_check": "A file is found",
        },
        {
            "id": "open",
            "capability_id": 2,
            "capability": "demo__open",
            "arguments": {"file_id": "${find.references[0].id}"},
            "depends_on": ["find"],
            "completion_check": "The file is opened",
        },
    ])
    calls: list[tuple[str, dict]] = []

    async def execute(action, arguments, contract):
        calls.append((action.id, arguments))
        if action.id == "find":
            return {
                "success": True,
                "resource_refs": [{"type": "file", "id": 42}],
            }
        return {"success": True, "opened": arguments["file_id"]}

    checkpoint = ActionPlanCheckpoint(plan=plan)
    executor = ActionGraphExecutor(
        catalog=_catalog(),
        execute_callback=execute,
        validator=OfflineValidator(user_id=4, catalog=_catalog()),
    )

    result = await executor.execute(checkpoint)

    assert result.status == ActionGraphStatus.COMPLETED
    assert calls == [("find", {"query": "report"}), ("open", {"file_id": 42})]
    assert checkpoint.observations["find"].references[0].id == 42
    assert checkpoint.observations["find"].references[0].provenance == {
        "capability": "demo__find",
        "action_id": "find",
    }


@pytest.mark.asyncio
async def test_executor_normalizes_legacy_contract_input_schema_aliases() -> None:
    catalog = _catalog()
    catalog["candidates"][1]["execution_contract"]["input_schema"] = {
        "type": "object",
        "properties": {
            "file_id": {"type": "int"},
            "refine": {"type": "bool"},
        },
    }
    plan = _plan([{
        "id": "open",
        "capability_id": 2,
        "capability": "demo__open",
        "arguments": {"file_id": 42, "refine": True},
        "completion_check": "The file is opened",
    }])
    calls: list[dict] = []

    async def execute(action, arguments, contract):
        calls.append(arguments)
        return {"success": True}

    checkpoint = ActionPlanCheckpoint(plan=plan)
    result = await ActionGraphExecutor(catalog=catalog, execute_callback=execute).execute(checkpoint)

    assert result.status == ActionGraphStatus.COMPLETED
    assert calls == [{"file_id": 42, "refine": True}]


@pytest.mark.asyncio
async def test_executor_stops_on_failed_action_and_never_blindly_retries() -> None:
    plan = _plan([
        {
            "id": "find",
            "capability_id": 1,
            "capability": "demo__find",
            "arguments": {"query": "missing"},
            "completion_check": "A file is found",
        },
        {
            "id": "open",
            "capability_id": 2,
            "capability": "demo__open",
            "arguments": {"file_id": 1},
            "depends_on": ["find"],
            "completion_check": "The file is opened",
        },
    ])
    calls: list[str] = []

    async def execute(action, arguments, contract):
        calls.append(action.id)
        return {"success": False, "error": "not found"}

    checkpoint = ActionPlanCheckpoint(plan=plan)
    executor = ActionGraphExecutor(catalog=_catalog(), execute_callback=execute)

    first = await executor.execute(checkpoint)
    second = await executor.execute(checkpoint)

    assert first.status == ActionGraphStatus.FAILED
    assert second.status == ActionGraphStatus.FAILED
    assert calls == ["find"]
    assert checkpoint.observations["find"].retryable is False
    assert "open" not in checkpoint.observations


@pytest.mark.asyncio
async def test_executor_returns_blocked_for_required_approval() -> None:
    plan = _plan([{
        "id": "write",
        "capability_id": 3,
        "capability": "demo__write",
        "arguments": {},
        "completion_check": "Write completes",
    }])

    async def execute(action, arguments, contract):
        return {
            "success": False,
            "error": "Approval is required.",
            "error_class": "approval_required",
            "approval_id": 7,
        }

    checkpoint = ActionPlanCheckpoint(plan=plan)
    result = await ActionGraphExecutor(
        catalog=_catalog(),
        execute_callback=execute,
    ).execute(checkpoint)

    assert result.status == ActionGraphStatus.BLOCKED
    assert checkpoint.observations["write"].state.value == "blocked"
    assert checkpoint.observations["write"].retryable is False


@pytest.mark.asyncio
async def test_executor_parallelizes_only_contract_safe_actions() -> None:
    plan = _plan([
        {
            "id": "read_one",
            "capability_id": 1,
            "capability": "demo__find",
            "arguments": {"query": "one"},
            "completion_check": "First read completes",
        },
        {
            "id": "read_two",
            "capability_id": 2,
            "capability": "demo__open",
            "arguments": {"file_id": 2},
            "completion_check": "Second read completes",
        },
        {
            "id": "write",
            "capability_id": 3,
            "capability": "demo__write",
            "arguments": {},
            "completion_check": "Write completes",
        },
    ])
    active = 0
    max_active = 0
    completed: list[str] = []

    async def execute(action, arguments, contract):
        nonlocal active, max_active
        if action.id == "write":
            assert active == 0
        active += 1
        max_active = max(max_active, active)
        await asyncio.sleep(0.01)
        active -= 1
        completed.append(action.id)
        return {"success": True}

    result = await ActionGraphExecutor(
        catalog=_catalog(),
        execute_callback=execute,
        max_concurrency=2,
    ).execute(ActionPlanCheckpoint(plan=plan))

    assert result.status == ActionGraphStatus.COMPLETED
    assert max_active == 2
    assert completed[-1] == "write"
