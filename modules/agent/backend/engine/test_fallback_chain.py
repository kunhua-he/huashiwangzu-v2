"""Tests for fallback_chain.py — model fallback chain."""
import pytest

from . import engine as engine_module
from . import fallback_chain as fallback_chain_module
from .fallback_chain import _extract_reason


class _CountingGateway:
    def __init__(self) -> None:
        self.chat_calls: list[dict] = []
        self.stream_calls: list[dict] = []

    async def chat(
        self,
        messages: list[dict],
        profile_key: str,
        tools: list[dict] | None = None,
    ) -> dict:
        self.chat_calls.append({
            "messages": messages,
            "profile_key": profile_key,
            "tools": tools,
        })
        return {"content": "gateway result", "error": "upstream exhausted"}

    async def chat_stream(
        self,
        messages: list[dict],
        profile_key: str,
        tools: list[dict] | None = None,
    ):
        self.stream_calls.append({
            "messages": messages,
            "profile_key": profile_key,
            "tools": tools,
        })
        yield {"type": "degradation", "content": "primary -> fallback"}
        yield {"type": "token", "content": "partial"}
        yield {"type": "error", "content": "gateway exhausted"}


class TestExtractReason:
    def test_basic_exception(self):
        e = ValueError("connection refused")
        reason = _extract_reason(e)
        assert "connection refused" in reason

    def test_truncated_message(self):
        e = ValueError("x" * 500)
        reason = _extract_reason(e)
        assert len(reason) <= 310


@pytest.mark.asyncio
async def test_chat_with_degradation_chain_delegates_to_gateway_once(monkeypatch: pytest.MonkeyPatch) -> None:
    gateway = _CountingGateway()
    monkeypatch.setattr(fallback_chain_module, "gateway_router", gateway)
    messages = [{"role": "user", "content": "hello"}]
    tools = [{"type": "function", "function": {"name": "demo"}}]

    result = await engine_module.chat_with_degradation_chain(
        messages=messages,
        profile_key="primary-model",
        tools=tools,
        conversation_id=123,
    )

    assert result == {"content": "gateway result", "error": "upstream exhausted"}
    assert gateway.chat_calls == [{
        "messages": messages,
        "profile_key": "primary-model",
        "tools": tools,
    }]


@pytest.mark.asyncio
async def test_chat_stream_with_degradation_chain_passes_gateway_events_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gateway = _CountingGateway()
    monkeypatch.setattr(fallback_chain_module, "gateway_router", gateway)
    messages = [{"role": "user", "content": "hello"}]

    events = [
        event
        async for event in engine_module.chat_stream_with_degradation_chain(
            messages=messages,
            profile_key="primary-model",
            tools=None,
            conversation_id=456,
        )
    ]

    assert events == [
        {"type": "degradation", "content": "primary -> fallback"},
        {"type": "token", "content": "partial"},
        {"type": "error", "content": "gateway exhausted"},
    ]
    assert gateway.stream_calls == [{
        "messages": messages,
        "profile_key": "primary-model",
        "tools": None,
    }]
