from __future__ import annotations

import json

import pytest

from modules.agent.backend.engine import engine as engine_module
from modules.agent.backend.engine import fallback_chain as fallback_chain_module
from modules.agent.backend.runtime.action_planner import ActionPlanner, ActionPlannerError


def _catalog() -> dict:
    return {
        "catalog_hash": "a" * 64,
        "principal": {"profile_version": "b" * 20},
        "candidates": [
            {
                "capability_id": 11,
                "module": "desktop-tools",
                "action": "search_files",
                "brief": "Search authorized files",
                "parameters": {"query": {"type": "string"}},
                "execution_contract": {
                    "side_effect_level": "none",
                    "output_reference_types": ["file"],
                },
            },
            {
                "capability_id": 12,
                "module": "desktop-tools",
                "action": "open_file",
                "brief": "Open an authorized file",
                "parameters": {"file_id": {"type": "integer"}},
                "execution_contract": {"side_effect_level": "none"},
            },
        ],
    }


@pytest.mark.asyncio
async def test_planner_requests_structured_dag_and_binds_catalog_identity() -> None:
    captured: dict = {}

    async def model_call(**kwargs) -> dict:
        captured.update(kwargs)
        return {
            "content": json.dumps({
                "decision": "action_graph",
                "goal": "Locate and open the requested file",
                "answer": "",
                "actions": [
                    {
                        "id": "find",
                        "capability": "desktop-tools__search_files",
                        "arguments": {"query": "quarterly report"},
                        "depends_on": [],
                        "expected_references": ["file"],
                        "completion_check": "A file reference is returned",
                        "approval_reason": "",
                    },
                    {
                        "id": "open",
                        "capability": "desktop-tools__open_file",
                        "arguments": {"file_id": "${find.references[0].id}"},
                        "depends_on": ["find"],
                        "expected_references": [],
                        "completion_check": "The file is opened",
                        "approval_reason": "",
                    },
                ],
                "final_completion_check": "The requested file is open",
                "need_user_input": [],
            }),
        }

    planner = ActionPlanner(profile_key="demo", model_call=model_call)
    plan = await planner.plan(
        goal="Open the quarterly report",
        catalog=_catalog(),
        messages=[{"role": "system", "content": "Plan authorized actions."}],
    )

    assert plan.catalog_hash == "a" * 64
    assert plan.principal_version == "b" * 20
    assert [item.capability_id for item in plan.actions] == [11, 12]
    assert plan.actions[1].depends_on == ["find"]
    response_format = captured["response_format"]
    assert response_format["type"] == "json_schema"
    action_schema = response_format["json_schema"]["schema"]["$defs"]["PlannedAction"]
    assert action_schema["properties"]["capability"]["enum"] == [
        "desktop-tools__search_files",
        "desktop-tools__open_file",
    ]
    planning_context = json.loads(captured["messages"][-1]["content"])
    assert planning_context["output_contract"]["format"].startswith("Return exactly one JSON object")
    assert planning_context["output_contract"]["schema"] == response_format["json_schema"]["schema"]


@pytest.mark.asyncio
async def test_planner_can_return_direct_answer_without_capabilities() -> None:
    async def model_call(**kwargs) -> dict:
        return {
            "content": json.dumps({
                "decision": "direct_answer",
                "goal": "Answer the greeting",
                "answer": "Hello",
                "actions": [],
                "final_completion_check": "The user is answered",
                "need_user_input": [],
            }),
        }

    catalog = _catalog()
    catalog["candidates"] = []
    result = await ActionPlanner(profile_key="demo", model_call=model_call).decide(
        goal="hello",
        catalog=catalog,
    )

    assert result.decision == "direct_answer"
    assert result.answer == "Hello"
    assert result.plan is None


@pytest.mark.asyncio
async def test_planner_can_request_required_user_input() -> None:
    async def model_call(**kwargs) -> dict:
        return {
            "content": json.dumps({
                "decision": "need_user_input",
                "goal": "Open a file",
                "answer": "Please identify the file.",
                "actions": [],
                "final_completion_check": "A file is identified",
                "need_user_input": ["Which file should I open?"],
            }),
        }

    result = await ActionPlanner(profile_key="demo", model_call=model_call).decide(
        goal="open it",
        catalog=_catalog(),
    )

    assert result.decision == "need_user_input"
    assert result.need_user_input == ["Which file should I open?"]


@pytest.mark.asyncio
async def test_planner_rejects_rounds_beyond_budget_without_calling_model() -> None:
    called = False

    async def model_call(**kwargs) -> dict:
        nonlocal called
        called = True
        return {}

    planner = ActionPlanner(
        profile_key="demo",
        model_call=model_call,
        max_planning_rounds=2,
    )

    with pytest.raises(ActionPlannerError, match="planning_round_limit_exceeded"):
        await planner.plan(goal="demo", catalog=_catalog(), planning_round=3)
    assert called is False


@pytest.mark.asyncio
async def test_planner_rejects_non_json_model_output() -> None:
    async def model_call(**kwargs) -> dict:
        return {"content": "I would call a tool."}

    planner = ActionPlanner(profile_key="demo", model_call=model_call)
    with pytest.raises(ActionPlannerError, match="invalid_structured_action_plan"):
        await planner.plan(goal="demo", catalog=_catalog())


@pytest.mark.asyncio
async def test_engine_fallback_chain_preserves_response_format(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict = {}

    class Gateway:
        async def chat(self, **kwargs) -> dict:
            captured["chat"] = kwargs
            return {"content": "{}"}

        async def chat_stream(self, **kwargs):
            captured["stream"] = kwargs
            yield {"type": "done", "content": ""}

    monkeypatch.setattr(fallback_chain_module, "gateway_router", Gateway())
    response_format = {"type": "json_object"}

    await engine_module.chat_with_degradation_chain(
        messages=[],
        profile_key="demo",
        response_format=response_format,
    )
    events = [
        event
        async for event in engine_module.chat_stream_with_degradation_chain(
            messages=[],
            profile_key="demo",
            response_format=response_format,
        )
    ]

    assert captured["chat"]["response_format"] == response_format
    assert captured["stream"]["response_format"] == response_format
    assert events == [{"type": "done", "content": ""}]
