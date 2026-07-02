"""Regression tests for Agent/Scheduler background task semantics."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


class _FakeConversation:
    processing = True


class _FakeScalarResult:
    def scalar_one_or_none(self) -> _FakeConversation:
        return _FakeConversation()


class _FakeSession:
    async def __aenter__(self) -> "_FakeSession":
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None

    async def execute(self, *args: object, **kwargs: object) -> _FakeScalarResult:
        return _FakeScalarResult()

    async def commit(self) -> None:
        return None


@pytest.mark.asyncio
async def test_slow_tool_failure_returns_failed_semantics_and_notifies_with_whitelisted_system(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app import database as app_database

    from modules.agent.backend.handlers import tasks
    from modules.agent.backend.services import conversation_service

    calls: list[dict[str, object]] = []
    messages: list[str] = []

    async def fake_call_capability(
        target_module: str,
        action: str,
        params: dict,
        caller: str,
        caller_role: str = "viewer",
    ) -> dict:
        calls.append({
            "target_module": target_module,
            "action": action,
            "caller": caller,
            "caller_role": caller_role,
            "params": params,
        })
        if target_module == "im":
            return {"success": True}
        raise RuntimeError("tool boom")

    async def fake_add_message(
        db: object,
        owner_id: int,
        conversation_id: int,
        role: str,
        content: str,
    ) -> object:
        messages.append(content)
        return object()

    monkeypatch.setattr(tasks, "call_capability", fake_call_capability)
    monkeypatch.setattr(app_database, "AsyncSessionLocal", lambda: _FakeSession())
    monkeypatch.setattr(conversation_service, "add_message", fake_add_message)

    result = await tasks._handle_slow_tool({
        "conversation_id": 101,
        "owner_id": 7,
        "tool_name": "knowledge__search",
        "skill_args": {"query": "x"},
        "caller": "user:7",
        "caller_role": "viewer",
    })

    assert result["success"] is False
    assert result["status"] == "failed"
    assert result["error"] == "tool boom"
    assert any("执行失败" in message and "tool boom" in message for message in messages)

    notify_call = calls[-1]
    assert notify_call["target_module"] == "im"
    assert notify_call["caller"] == "system:task-worker"
    assert notify_call["caller_role"] == "viewer"


@pytest.mark.asyncio
async def test_scheduler_uses_creator_or_whitelisted_system_callers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services import module_registry

    from modules.scheduler.backend import router as scheduler_router

    calls: list[dict[str, object]] = []

    async def fake_call_capability(
        target_module: str,
        action: str,
        params: dict,
        caller: str,
        caller_role: str = "viewer",
    ) -> dict:
        calls.append({
            "target_module": target_module,
            "action": action,
            "caller": caller,
            "caller_role": caller_role,
            "params": params,
        })
        if target_module == "agent":
            return {
                "success": True,
                "data": {"results": [{"status": "completed", "conclusion": "done"}]},
            }
        return {"success": True}

    monkeypatch.setattr(module_registry, "call_capability", fake_call_capability)

    result = await scheduler_router._cap_scheduled_job_handler({
        "title": "daily",
        "action_description": "请总结今天的项目状态并提醒我。",
        "creator_id": 42,
    })

    assert result["success"] is True
    assert calls[0]["target_module"] == "agent"
    assert calls[0]["caller"] == "user:42"
    assert calls[0]["caller_role"] == "viewer"
    assert calls[1]["target_module"] == "im"
    assert calls[1]["caller"] == "system:task-worker"
    assert calls[1]["caller_role"] == "viewer"
