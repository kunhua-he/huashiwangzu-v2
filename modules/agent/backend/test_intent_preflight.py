from __future__ import annotations

import pytest

from modules.agent.backend.runtime.intent_preflight import IntentPreflightRunner, _parse_json_object, _rule_classify
from modules.agent.backend.runtime.runtime_policy import RuntimePolicy


def test_operation_path_is_rule_first_and_not_clarify_only() -> None:
    result = _rule_classify("某个系统里哪个页面可以看到数据？")

    assert result.task_category == "operation_path"
    assert result.answer_shape == "menu_path"
    assert result.evidence_policy.needs_internal_knowledge is True


def test_creation_routes_to_direct_answer() -> None:
    result = _rule_classify("帮我写一段新品宣传文案")

    assert result.task_category == "creation"
    assert result.answer_shape == "direct_answer"
    assert result.evidence_policy.can_answer_from_general_knowledge is True


def test_external_research_requires_source_strategy() -> None:
    result = _rule_classify("帮我查一下网上最新的行业新闻")

    assert result.task_category == "external_research"
    assert result.evidence_policy.needs_external_web is True
    assert result.risk_policy.requires_citation is True
    assert result.tool_strategy.suggested_queries


def test_internal_knowledge_routes_to_internal_retrieval() -> None:
    result = _rule_classify("公司内部制度是什么？")

    assert result.task_category == "internal_knowledge"
    assert result.evidence_policy.needs_internal_knowledge is True
    assert result.tool_strategy.suggested_queries


@pytest.mark.asyncio
async def test_internal_knowledge_injection_contains_stop_condition() -> None:
    policy = RuntimePolicy.default()
    runner = IntentPreflightRunner(
        conversation_id=1,
        owner_id=1,
        profile_key="deepseek-v4-flash",
        policy=policy,
    )
    result = _rule_classify("公司内部流程怎么查")

    injection = await runner.build_injection(result)

    assert "停止条件" in injection
    assert "已有与请求相关的证据结果" in injection
    assert "没有足够证据时不要断言" in injection


def test_too_vague_request_is_clarification_shape() -> None:
    result = _rule_classify("帮我弄一下")

    assert result.answer_shape == "clarification"
    assert result.evidence_policy.should_ask_clarification is True


@pytest.mark.asyncio
async def test_rules_mode_does_not_call_llm() -> None:
    calls = 0

    async def fake_chat(_messages: list[dict], _profile: str) -> dict:
        nonlocal calls
        calls += 1
        return {"content": "{}"}

    policy = RuntimePolicy.default()
    policy.intent_preflight_mode = "rules"
    policy.intent_preflight_max_llm_calls = 0
    runner = IntentPreflightRunner(
        conversation_id=1,
        owner_id=1,
        profile_key="deepseek-v4-flash",
        policy=policy,
        chat_fn=fake_chat,
    )

    result = await runner.run("某个系统里哪个页面可以看到数据？")

    assert result.task_category == "operation_path"
    assert calls == 0


def test_parse_json_object_strips_markdown_fence() -> None:
    parsed = _parse_json_object('```json\n{"task_category":"creation"}\n```')

    assert parsed["task_category"] == "creation"
