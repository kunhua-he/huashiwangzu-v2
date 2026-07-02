"""Regression tests for ToolLoopRuntime safety helpers."""

import sys
from collections.abc import AsyncIterator
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from modules.agent.backend.engine.stuck_detector import reset
from modules.agent.backend.runtime import tool_loop_runtime
from modules.agent.backend.runtime.runtime_policy import RuntimePolicy
from modules.agent.backend.runtime.stream_emitter import StreamEmitter
from modules.agent.backend.runtime.tool_loop_runtime import ToolLoopRuntime, detect_tool_round_stuck
from modules.agent.backend.services.model_client import final_clean_content


def _tool_call(name: str = "search", args: dict | None = None) -> dict:
    return {
        "id": "call_1",
        "type": "function",
        "function": {"name": name, "arguments": args or {"q": "hello"}},
    }


class TestToolRoundStuckDetection:
    def setup_method(self):
        reset("runtime_test")

    def test_same_round_duplicate_calls_count_once(self):
        duplicate_calls = [_tool_call(), _tool_call(), _tool_call()]
        result = detect_tool_round_stuck(duplicate_calls, "runtime_test")
        assert not result["stuck"]

    def test_duplicate_calls_across_rounds_still_trigger(self):
        for _ in range(3):
            result = detect_tool_round_stuck([_tool_call()], "runtime_test")
        assert result["stuck"]


def test_final_event_content_uses_cleaned_text():
    raw = '正文<invoke name="tool"><parameter name="x">1</parameter></invoke>结尾'
    clean_content = final_clean_content(raw)
    pending_event = {"event_type": "assistant_msg", "payload": {"content": clean_content}}
    assert "<invoke" not in pending_event["payload"]["content"]
    assert pending_event["payload"]["content"] == "正文结尾"


@pytest.mark.asyncio
async def test_streaming_unfinished_tool_intent_returns_retry_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_stream(*args: object, **kwargs: object) -> AsyncIterator[dict]:
        yield {"type": "token", "content": "这个问题我帮你联网查一下最新信息。"}
        yield {"type": "done", "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}

    monkeypatch.setattr(tool_loop_runtime, "chat_stream_with_degradation_chain", fake_stream)

    runtime = ToolLoopRuntime(conversation_id=1, owner_id=1)
    full: list[str] = []
    timeline: list[dict] = []
    events: list[object] = []
    async for event in runtime._stream_until_tool_or_done(
        [{"role": "user", "content": "查一下"}],
        [{"type": "function", "function": {"name": "skill_use"}}],
        full,
        [],
        timeline,
        StreamEmitter(),
    ):
        events.append(event)

    result_events = [
        event.get("result", {})
        for event in events
        if isinstance(event, dict) and event.get("type") == "_stream_result"
    ]
    assert len(result_events) == 1
    assert result_events[0]["retry_tool_intent"] is True
    assert "error" not in result_events[0]
    assert full == []
    assert any(
        isinstance(event, bytes)
        and b"assistant_stream_rollback" in event
        and b"unfinished_tool_intent" in event
        for event in events
    )
    assert any(
        item.get("type") == "assistant_draft"
        and item.get("reason") == "rollback:unfinished_tool_intent"
        for item in timeline
    )


class _DummySession:
    async def __aenter__(self) -> "_DummySession":
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None

    async def execute(self, *args: object, **kwargs: object) -> None:
        raise RuntimeError("skip database in unit test")


class _FakeSink:
    def __init__(self) -> None:
        self.persisted_content = ""

    async def record_failure(self, *args: object, **kwargs: object) -> None:
        return None

    async def persist_assistant(
        self,
        db: object,
        content: str,
        thinking_parts: list[str],
        tool_events: list[dict],
        timeline: list[dict],
        usage: dict | None = None,
    ) -> int:
        self.persisted_content = content
        return 123

    async def persist_pending_events(
        self,
        db: object,
        pending_events: list[dict],
        persisted_event_count: int,
    ) -> int:
        return len(pending_events)

    async def generate_completion_evidence(
        self,
        tool_events: list[dict],
        tool_results: list[dict],
    ) -> list[dict]:
        return []

    def check_tool_success(self, tool_events: list[dict]) -> bool:
        return True

    async def record_trajectory(self, *args: object, **kwargs: object) -> dict:
        return {"recorded": False}

    async def run_post_turn_hooks(self, *args: object, **kwargs: object) -> None:
        return None


@pytest.mark.asyncio
async def test_run_retries_streaming_tool_intent_without_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    call_count = 0

    async def fake_stream_until_tool_or_done(
        self: ToolLoopRuntime,
        messages: list[dict],
        tools: list[dict] | None,
        full: list[str],
        thinking_parts: list[str],
        timeline: list[dict],
        emitter: StreamEmitter,
    ) -> AsyncIterator[object]:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            yield {
                "type": "_stream_result",
                "result": {
                    "content": "这个问题我帮你联网查一下最新信息。",
                    "retry_tool_intent": True,
                    "retry_message": tool_loop_runtime.TOOL_INTENT_RETRY_MESSAGE,
                    "usage": {},
                },
            }
            return
        full.append("已完成回答。")
        yield {
            "type": "_stream_result",
            "result": {
                "content": "已完成回答。",
                "tool_calls": [],
                "finish_reason": "stop",
                "usage": {},
            },
        }

    monkeypatch.setattr(
        ToolLoopRuntime,
        "_stream_until_tool_or_done",
        fake_stream_until_tool_or_done,
    )
    monkeypatch.setattr(tool_loop_runtime, "AsyncSessionLocal", lambda: _DummySession())

    policy = RuntimePolicy(max_tool_rounds=2, enable_single_pass_streaming_tools=True)
    runtime = ToolLoopRuntime(conversation_id=1, owner_id=1, policy=policy)
    messages = [{"role": "user", "content": "查一下"}]
    sink = _FakeSink()

    events: list[object] = []
    async for event in runtime.run(
        messages,
        [{"type": "function", "function": {"name": "skill_use"}}],
        sink,  # type: ignore[arg-type]
    ):
        events.append(event)

    assert call_count == 2
    assert sink.persisted_content == "已完成回答。"
    assert any(
        message.get("role") == "user"
        and message.get("content") == tool_loop_runtime.TOOL_INTENT_RETRY_MESSAGE
        for message in messages
    )
    assert not any(
        isinstance(event, bytes) and b'"type": "error"' in event
        for event in events
    )
