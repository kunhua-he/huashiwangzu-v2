from __future__ import annotations

import pytest
from pydantic import ValidationError

from modules.agent.backend.runtime.action_plan import (
    ActionObservation,
    ActionPlan,
    ActionPlanCheckpoint,
    ActionState,
)


def _plan(actions: list[dict]) -> ActionPlan:
    return ActionPlan.model_validate({
        "goal": "Produce an authorized result",
        "catalog_hash": "a" * 64,
        "principal_version": "b" * 20,
        "actions": actions,
        "final_completion_check": "A typed result reference exists",
    })


def test_action_plan_validates_dag_and_ready_actions() -> None:
    plan = _plan([
        {
            "id": "find",
            "capability_id": 1,
            "capability": "desktop-tools__search_files",
            "completion_check": "A file reference exists",
        },
        {
            "id": "open",
            "capability_id": 2,
            "capability": "desktop-tools__open_file",
            "depends_on": ["find"],
            "completion_check": "The file was opened",
        },
    ])

    assert ActionPlanCheckpoint(plan=plan).ready_action_ids() == ["find"]


def test_failed_action_is_terminal_and_never_ready_again() -> None:
    plan = _plan([{
        "id": "find",
        "capability_id": 1,
        "capability": "desktop-tools__search_files",
        "completion_check": "A file reference exists",
    }])
    checkpoint = ActionPlanCheckpoint(
        plan=plan,
        observations={
            "find": ActionObservation(
                action_id="find",
                state=ActionState.FAILED,
                attempt=1,
            ),
        },
    )

    assert checkpoint.ready_action_ids() == []


def test_action_plan_rejects_cycles() -> None:
    with pytest.raises(ValidationError, match="acyclic"):
        _plan([
            {
                "id": "one",
                "capability_id": 1,
                "capability": "module__one",
                "depends_on": ["two"],
                "completion_check": "one",
            },
            {
                "id": "two",
                "capability_id": 2,
                "capability": "module__two",
                "depends_on": ["one"],
                "completion_check": "two",
            },
        ])


def test_structured_resume_retries_only_interrupted_read_only_action() -> None:
    plan = _plan([
        {
            "id": "read",
            "capability_id": 1,
            "capability": "demo__read",
            "completion_check": "Read completes",
        },
        {
            "id": "write",
            "capability_id": 2,
            "capability": "demo__write",
            "completion_check": "Write completes",
        },
    ])
    checkpoint = ActionPlanCheckpoint(
        plan=plan,
        observations={
            action_id: ActionObservation(
                action_id=action_id,
                state=ActionState.RUNNING,
                attempt=1,
            )
            for action_id in ("read", "write")
        },
    )
    catalog = {
        "candidates": [
            {
                "module": "demo",
                "action": "read",
                "execution_contract": {"side_effect_level": "none"},
            },
            {
                "module": "demo",
                "action": "write",
                "execution_contract": {"side_effect_level": "update"},
            },
        ],
    }

    checkpoint.reconcile_interrupted_actions(catalog)

    assert checkpoint.observations["read"].state == ActionState.PENDING
    assert checkpoint.observations["read"].retryable is True
    assert checkpoint.observations["write"].state == ActionState.BLOCKED
    assert checkpoint.ready_action_ids() == ["read"]
