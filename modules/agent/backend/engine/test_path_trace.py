from __future__ import annotations

from .path_trace import build_path_trace_summary


def test_path_trace_records_recipe_and_tool_usage() -> None:
    payload = build_path_trace_summary(
        user_input="娇薇诗有什么产品",
        assistant_text="根据知识库资料，娇薇诗产品包括娇韵皓芙霜，来源 42。",
        intent_preflight={
            "task_category": "internal_knowledge",
            "answer_shape": "fact",
            "intent_summary": "用户需要内部知识或企业资料",
            "confidence": 0.8,
            "domain_terms": ["娇薇诗", "产品"],
            "tool_strategy": {"first_actions": ["match_experience", "internal_retrieval"]},
            "evidence_policy": {"needs_internal_knowledge": True},
            "risk_policy": {"requires_citation": True},
            "matched_experiences": [{"id": 9}],
        },
        route_diagnostics={
            "recipe_injected": 1,
            "recipe_labels": ["知识库产品问答"],
            "experience_injected": [9],
        },
        tool_events=[
            {
                "type": "tool_call",
                "name": "skill_use",
                "tool_call_id": "call_1",
                "arguments": {"name": "knowledge__search", "args": {"query": "娇薇诗 产品"}},
            },
            {
                "type": "tool_result",
                "name": "skill_use",
                "effective_tool_name": "knowledge__search",
                "tool_call_id": "call_1",
                "duration_ms": 320,
                "result": {
                    "success": True,
                    "data": {
                        "query_context_id": 42,
                        "results": [{"document_name": "娇薇诗 价目表", "chunk_id": 7}],
                    },
                },
            },
        ],
        timeline=[{"type": "tool_result", "duration_ms": 320}],
        usage={"prompt_tokens": 100, "completion_tokens": 30, "model_call_count": 2, "work_duration_ms": 1500},
        message_id=5,
    )

    assert payload["intent"]["task_category"] == "internal_knowledge"
    assert payload["recipe_match"]["matched"] is True
    assert payload["recipe_match"]["labels"] == ["知识库产品问答"]
    assert payload["experience_match"]["matched"] is True
    assert payload["stop_condition"]["reason"] == "final_answer_after_tools"
    assert payload["tool_path"]["call_count"] == 1
    assert payload["tool_path"]["steps"][0]["effective_tool_name"] == "knowledge__search"
    assert payload["tool_path"]["steps"][0]["result_usage"] == "used"
    assert "knowledge_retrieval_reflect" in payload["learning"]["post_turn_tasks"]


def test_path_trace_direct_answer_without_tools() -> None:
    payload = build_path_trace_summary(
        user_input="你好",
        assistant_text="你好，有什么我可以帮你？",
        intent_preflight={"task_category": "smalltalk", "answer_shape": "direct_answer"},
        route_diagnostics={},
        tool_events=[],
        timeline=[{"type": "work_summary", "duration_ms": 100}],
        usage={"model_call_count": 1},
    )

    assert payload["stop_condition"]["reason"] == "direct_answer"
    assert payload["tool_path"]["call_count"] == 0
    assert payload["learning"]["mode"] == "async"
