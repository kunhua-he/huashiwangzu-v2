from __future__ import annotations

import os
from dataclasses import asdict

os.environ.setdefault("JWT_SECRET", "test-secret")

from app.gateway.tool_call_accumulator import StreamingToolCallAccumulator


def test_accumulates_single_tool_arguments_chunks() -> None:
    acc = StreamingToolCallAccumulator()
    acc.add_delta_tool_calls([
        {"index": 0, "id": "call_1", "type": "function", "function": {"name": "knowledge__search", "arguments": "{\"query\":"}},
    ])
    acc.add_delta_tool_calls([
        {"index": 0, "function": {"arguments": "\"华世王镞\"}"}},
    ])

    calls = [asdict(call) for call in acc.completed_tool_calls()]

    assert calls == [{
        "id": "call_1",
        "type": "function",
        "function": {"name": "knowledge__search", "arguments": "{\"query\":\"华世王镞\"}"},
    }]


def test_accumulates_interleaved_parallel_tools_by_index() -> None:
    acc = StreamingToolCallAccumulator()
    acc.add_delta_tool_calls([
        {"index": 1, "id": "call_b", "function": {"name": "desktop-tools__read_file", "arguments": "{\"path\":"}},
        {"index": 0, "id": "call_a", "function": {"name": "web-tools__search", "arguments": "{\"query\":"}},
    ])
    acc.add_delta_tool_calls([
        {"index": 0, "function": {"arguments": "\"agent\"}"}},
        {"index": 1, "function": {"arguments": "\"README.md\"}"}},
    ])

    calls = [asdict(call) for call in acc.completed_tool_calls()]

    assert [call["id"] for call in calls] == ["call_a", "call_b"]
    assert calls[0]["function"]["arguments"] == "{\"query\":\"agent\"}"
    assert calls[1]["function"]["arguments"] == "{\"path\":\"README.md\"}"


def test_preserves_malformed_arguments_as_raw_text() -> None:
    acc = StreamingToolCallAccumulator()
    acc.add_delta_tool_calls([
        {"index": 0, "id": "call_bad", "function": {"name": "x", "arguments": "{not-json"}},
    ])

    calls = acc.completed_tool_calls()

    assert calls[0].function["arguments"] == "{not-json"
