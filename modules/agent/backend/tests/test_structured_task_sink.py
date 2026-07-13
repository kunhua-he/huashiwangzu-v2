from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from app.schemas.platform_resource import ResourceRef

from modules.agent.backend.runtime import task_sink as task_sink_module
from modules.agent.backend.runtime.action_plan import (
    ActionObservation,
    ActionPlan,
    ActionPlanCheckpoint,
    ActionPlanItem,
    ActionState,
)
from modules.agent.backend.runtime.task_sink import (
    RuntimeTaskSink,
    resource_refs_from_checkpoint,
)


def _checkpoint(*, state: ActionState = ActionState.COMPLETED) -> ActionPlanCheckpoint:
    return ActionPlanCheckpoint(
        plan=ActionPlan(
            goal="Process /Users/example/private.txt with resource 987654",
            catalog_hash="catalog-hash-1234567890",
            principal_version="principal-version-1",
            actions=[
                ActionPlanItem(
                    id="find",
                    capability_id=11,
                    capability="desktop-tools__search_files",
                    arguments={"query": "private.txt", "file_id": 987654},
                    completion_check="Locate the requested private.txt file",
                    expected_references=["file"],
                ),
                ActionPlanItem(
                    id="read",
                    capability_id=12,
                    capability="desktop-tools__read_file",
                    arguments={"file_id": "${find.references[0].id}"},
                    depends_on=["find"],
                    completion_check="Read the requested file",
                ),
            ],
            final_completion_check="Return the private content",
        ),
        observations={
            "find": ActionObservation(
                action_id="find",
                state=state,
                attempt=1,
                result_summary='{"content":"raw private text","file_id":987654}',
                references=[
                    ResourceRef(
                        type="file",
                        id=987654,
                        display_name="private.txt",
                        provenance={
                            "capability": "desktop-tools__search_files",
                            "action_id": "find",
                        },
                    ),
                ],
            ),
            "read": ActionObservation(
                action_id="read",
                state=state,
                attempt=1,
                result_summary="raw private text",
            ),
        },
    )


def test_resource_refs_come_only_from_completed_observations() -> None:
    checkpoint = _checkpoint()
    checkpoint.observations["read"].references = [
        ResourceRef(type="record", id="record-1"),
        ResourceRef(type="file", id=987654),
    ]

    refs = resource_refs_from_checkpoint(checkpoint)

    assert [(item.type.value, item.id) for item in refs] == [
        ("file", 987654),
        ("record", "record-1"),
    ]
    checkpoint.observations["find"].state = ActionState.FAILED
    assert [(item.type.value, item.id) for item in resource_refs_from_checkpoint(checkpoint)] == [
        ("record", "record-1"),
        ("file", 987654),
    ]


@pytest.mark.asyncio
async def test_completion_evidence_uses_action_observations_and_resource_refs() -> None:
    sink = RuntimeTaskSink(conversation_id=8, owner_id=4)

    evidence = await sink.generate_completion_evidence(_checkpoint())

    assert evidence[0]["capability"] == "desktop-tools__search_files"
    assert evidence[0]["contract_verified"] is True
    assert evidence[0]["resource_refs"][0]["type"] == "file"
    assert evidence[0]["resource_refs"][0]["id"] == 987654
    serialized = json.dumps(evidence)
    assert "operation" not in serialized
    assert "read_back_verified" not in serialized
    assert "artifact_ids" not in serialized


@pytest.mark.asyncio
async def test_completed_experience_is_structured_and_contains_no_resource_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict = {}

    async def fake_call_capability(
        target_module: str,
        action: str,
        params: dict,
        caller: str,
        caller_role: str,
        *,
        actor: str,
    ) -> dict:
        captured.update({
            "target_module": target_module,
            "action": action,
            "params": params,
            "caller": caller,
            "caller_role": caller_role,
            "actor": actor,
        })
        return {"success": True, "data": {"id": 31}}

    monkeypatch.setattr(task_sink_module, "call_capability", fake_call_capability)
    sink = RuntimeTaskSink(conversation_id=8, owner_id=4)

    checkpoint = _checkpoint()
    result = await sink.submit_completed_experience(checkpoint)

    assert result == {"submitted": True, "result": {"id": 31}}
    assert captured["target_module"] == "memory"
    assert captured["action"] == "save_experience"
    assert captured["caller"] == "user:4"
    assert captured["actor"] == "system:agent-engine"
    params = captured["params"]
    assert params["action_pattern"] == [
        {
            "id": "find",
            "capability": "desktop-tools__search_files",
            "depends_on": [],
            "expected_references": ["file"],
        },
        {
            "id": "read",
            "capability": "desktop-tools__read_file",
            "depends_on": ["find"],
            "expected_references": [],
        },
    ]
    serialized = json.dumps(params, ensure_ascii=False)
    assert "987654" not in serialized
    assert "private.txt" not in serialized
    assert "raw private text" not in serialized
    assert "arguments" not in serialized
    assert params["completion_evidence"]["reference_types"] == ["file"]
    assert checkpoint.experience_submitted is True
    assert checkpoint.experience_id == 31
    assert await sink.submit_completed_experience(checkpoint) == {
        "submitted": False,
        "reason": "already_submitted",
        "experience_id": 31,
    }


@pytest.mark.asyncio
async def test_incomplete_plan_does_not_submit_experience(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def unexpected_call(*args: object, **kwargs: object) -> dict:
        raise AssertionError("incomplete plans must not call memory")

    monkeypatch.setattr(task_sink_module, "call_capability", unexpected_call)
    result = await RuntimeTaskSink(
        conversation_id=8,
        owner_id=4,
    ).submit_completed_experience(_checkpoint(state=ActionState.FAILED))
    assert result == {"submitted": False, "reason": "plan_not_completed"}


@pytest.mark.asyncio
async def test_persist_assistant_accepts_only_explicit_resource_refs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict = {}

    async def fake_add_message(*args: object, **kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(id=21)

    async def fake_add_message_meta(*args: object, **kwargs: object) -> None:
        captured.update(kwargs)

    async def fake_record_event(*args: object, **kwargs: object) -> None:
        return None

    monkeypatch.setattr(task_sink_module.conv_svc, "add_message", fake_add_message)
    monkeypatch.setattr(task_sink_module.conv_svc, "add_message_meta", fake_add_message_meta)
    monkeypatch.setattr(task_sink_module, "_record_event", fake_record_event)
    sink = RuntimeTaskSink(conversation_id=8, owner_id=4)

    await sink.persist_assistant(
        object(),
        "Done",
        [],
        [{"type": "tool_result", "result": {"data": {"file_id": 999}}}],
        [],
        resource_refs=[ResourceRef(type="record", id="safe-record")],
    )

    assert captured["references"] == [{
        "id": "safe-record",
        "type": "record",
        "label": "",
        "version": None,
        "locator": "",
        "mime_type": "",
        "display_name": "",
        "access_scope": "user",
        "provenance": {},
    }]


@pytest.mark.asyncio
async def test_record_assets_uses_only_file_resource_refs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict] = []

    class DummySession:
        async def __aenter__(self) -> "DummySession":
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

    async def fake_create_asset(db: object, **kwargs: object) -> SimpleNamespace:
        calls.append(kwargs)
        return SimpleNamespace(id=70 + len(calls))

    from app.services import asset_service

    monkeypatch.setattr(task_sink_module, "AsyncSessionLocal", DummySession)
    monkeypatch.setattr(asset_service, "create_asset", fake_create_asset)
    sink = RuntimeTaskSink(conversation_id=8, owner_id=4)
    refs = [
        ResourceRef(
            type="file",
            id=42,
            provenance={"capability": "office-gen__docx", "action_id": "create"},
        ),
        ResourceRef(type="record", id=42),
        ResourceRef(type="file", id="not-numeric"),
    ]

    asset_ids = await sink.record_assets(refs)

    assert asset_ids == [71]
    assert calls == [{
        "file_id": 42,
        "owner_id": 4,
        "asset_type": "generated",
        "conversation_id": 8,
        "tool_name": "office-gen__docx",
        "tool_call_id": "create",
    }]
