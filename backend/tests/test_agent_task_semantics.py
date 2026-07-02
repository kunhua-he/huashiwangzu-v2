"""Agent task semantics for event persistence and background memory jobs."""
import importlib
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

gateway_router_module = importlib.import_module("app.gateway.router")
_result_is_semantic_failure = importlib.import_module(
    "app.services.task_worker"
)._result_is_semantic_failure
agent_tasks = importlib.import_module("modules.agent.backend.handlers.tasks")
task_sink = importlib.import_module("modules.agent.backend.runtime.task_sink")
RuntimeTaskSink = task_sink.RuntimeTaskSink


@pytest.mark.asyncio
async def test_persist_pending_events_advances_only_contiguous_successes(monkeypatch) -> None:
    sink = RuntimeTaskSink(conversation_id=7, owner_id=4)
    calls: list[str] = []

    async def fake_record_event(_db, _conversation_id, event_type, _payload, _llm_response_id):
        calls.append(event_type)
        if event_type == "tool_call":
            raise RuntimeError("db insert failed")

    monkeypatch.setattr(task_sink, "_record_event", fake_record_event)

    pending = [
        {"event_type": "assistant_msg", "payload": {"content": "a"}},
        {"event_type": "tool_call", "payload": {"name": "x"}},
        {"event_type": "tool_result", "payload": {"ok": True}},
    ]

    persisted = await sink.persist_pending_events(object(), pending, persisted_count=0)

    assert persisted == 1
    assert calls == ["assistant_msg", "tool_call"]


@pytest.mark.asyncio
async def test_memory_distill_gateway_failure_is_worker_failure(monkeypatch) -> None:
    async def fake_chat(**_kwargs):
        return {"content": "", "error": "quota exhausted"}

    monkeypatch.setattr(gateway_router_module.gateway_router, "chat", fake_chat)

    result = await agent_tasks._submit_memory_distill_task(1, 4, "用户内容", "助手内容")
    failed, error = _result_is_semantic_failure(result)

    assert failed is True
    assert error == "quota exhausted"


@pytest.mark.asyncio
async def test_memory_distill_no_facts_is_skipped(monkeypatch) -> None:
    async def fake_chat(**_kwargs):
        return {"content": "[]"}

    monkeypatch.setattr(gateway_router_module.gateway_router, "chat", fake_chat)

    result = await agent_tasks._submit_memory_distill_task(1, 4, "你好", "你好")
    failed, error = _result_is_semantic_failure(result)

    assert result["status"] == "skipped"
    assert result["reason"] == "no_memory_facts"
    assert failed is False
    assert error is None


@pytest.mark.asyncio
async def test_memory_distill_save_failure_is_worker_failure(monkeypatch) -> None:
    async def fake_chat(**_kwargs):
        return {"content": '[{"text":"用户正在开发华世王镞 V2 项目，需要稳定的底层链路"}]'}

    async def fake_call_capability(*_args, **_kwargs):
        return {"success": False, "error": "memory unavailable"}

    monkeypatch.setattr(gateway_router_module.gateway_router, "chat", fake_chat)
    monkeypatch.setattr(agent_tasks, "call_capability", fake_call_capability)

    result = await agent_tasks._submit_memory_distill_task(1, 4, "用户内容", "助手内容")
    failed, error = _result_is_semantic_failure(result)

    assert failed is True
    assert error == "memory unavailable"


@pytest.mark.asyncio
async def test_memory_dream_empty_result_is_worker_failure(monkeypatch) -> None:
    from modules.agent.backend.engine import layered_memory

    async def fake_trigger_dream(_owner_id):
        return {}

    monkeypatch.setattr(layered_memory, "trigger_dream", fake_trigger_dream)

    result = await agent_tasks._handle_memory_dream({"owner_id": 4})
    failed, error = _result_is_semantic_failure(result)

    assert failed is True
    assert error == "memory dream returned no result"
