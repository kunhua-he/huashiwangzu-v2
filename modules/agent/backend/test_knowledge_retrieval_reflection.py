import pytest

from modules.agent.backend.handlers import tasks as task_handlers
from modules.agent.backend.runtime.task_sink import (
    build_retrieval_reflection_excerpt,
    extract_query_context_ids,
)


def test_extract_query_context_ids_from_nested_tool_payload() -> None:
    payload = [
        {
            "type": "tool_result",
            "name": "knowledge__search",
            "result": {
                "success": True,
                "data": {
                    "context_data": {
                        "query_context": {"query_context_id": 33},
                    },
                },
            },
        },
        {"result": "{\"query_context_id\": 33}"},
        {"result": {"query_context_id": "34"}},
    ]

    assert extract_query_context_ids(payload) == [33, 34]


def test_build_retrieval_reflection_excerpt_prefers_current_turn() -> None:
    excerpt = build_retrieval_reflection_excerpt(
        user_input="娇薇诗有什么检测报告没？给我个名单",
        assistant_text="找到 5 份产品安全评估报告。",
        messages=[{"role": "user", "content": "旧消息"}],
    )

    assert "用户本轮问题" in excerpt
    assert "助手本轮回答" in excerpt
    assert "娇薇诗" in excerpt
    assert "产品安全评估报告" in excerpt


@pytest.mark.asyncio
async def test_knowledge_reflection_handler_preserves_owner(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []

    async def fake_call_capability(module: str, action: str, params: dict, caller: str, caller_role: str) -> dict:
        calls.append({
            "module": module,
            "action": action,
            "params": params,
            "caller": caller,
            "caller_role": caller_role,
        })
        return {"inserted": 1, "updated": 0, "skipped": 0}

    monkeypatch.setattr(task_handlers, "call_capability", fake_call_capability)

    result = await task_handlers._handle_knowledge_retrieval_reflect({
        "owner_id": 4,
        "conversation_id": 99,
        "query_context_ids": [33, "33", 34],
        "conversation_excerpt": "用户确认这些检测报告是有效候选。",
    })

    assert result["status"] == "ok"
    assert result["processed"] == 2
    assert result["inserted"] == 2
    assert [call["params"]["query_context_id"] for call in calls] == [33, 34]
    assert all(call["module"] == "knowledge" for call in calls)
    assert all(call["action"] == "reflect_retrieval_feedback" for call in calls)
    assert all(call["caller"] == "user:4" for call in calls)
    assert all(call["caller_role"] == "admin" for call in calls)
