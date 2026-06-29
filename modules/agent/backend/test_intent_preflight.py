from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("JWT_SECRET", "test-secret")

REPO_DIR = Path(__file__).resolve().parents[3]
BACKEND_DIR = REPO_DIR / "backend"
for path in (REPO_DIR, BACKEND_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

PREFLIGHT_PATH = REPO_DIR / "modules/agent/backend/runtime/intent_preflight.py"
spec = importlib.util.spec_from_file_location("modules.agent.backend.runtime.intent_preflight", PREFLIGHT_PATH)
assert spec and spec.loader
preflight = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preflight)

IntentPreflightRunner = preflight.IntentPreflightRunner
_parse_json_object = preflight._parse_json_object
_rule_classify = preflight._rule_classify

from modules.agent.backend.runtime.runtime_policy import RuntimePolicy


def test_operation_path_is_rule_first_and_not_clarify_only() -> None:
    result = _rule_classify("某个系统里哪个页面可以看到数据？")

    assert result.task_category == "operation_path"
    assert result.answer_shape == "menu_path"
    assert result.tool_strategy.first_actions != ["clarify"]
    assert "answer_with_caveat" in result.tool_strategy.first_actions


def test_creation_routes_to_direct_answer() -> None:
    result = _rule_classify("帮我写一段新品宣传文案")

    assert result.task_category == "creation"
    assert result.answer_shape == "direct_answer"
    assert result.tool_strategy.first_actions == ["direct_answer"]


def test_external_research_requires_source_strategy() -> None:
    result = _rule_classify("帮我查一下网上最新的行业新闻")

    assert result.task_category == "external_research"
    assert result.evidence_policy.needs_external_web is True
    assert result.risk_policy.requires_citation is True
    assert "external_research" in result.tool_strategy.first_actions


def test_internal_knowledge_routes_to_internal_retrieval() -> None:
    result = _rule_classify("公司产品成分规格是什么？")

    assert result.task_category == "internal_knowledge"
    assert result.evidence_policy.needs_internal_knowledge is True
    assert "internal_retrieval" in result.tool_strategy.first_actions


def test_too_vague_request_is_clarification_shape() -> None:
    result = _rule_classify("帮我弄一下")

    assert result.answer_shape == "clarification"
    assert result.tool_strategy.first_actions == ["clarify"]


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
        match_experience_fn=_fake_match_experience,
    )

    result = await runner.run("某个系统里哪个页面可以看到数据？")

    assert result.task_category == "operation_path"
    assert calls == 0


@pytest.mark.asyncio
async def test_runner_matches_experience_from_rule_queries() -> None:
    policy = RuntimePolicy.default()
    runner = IntentPreflightRunner(
        conversation_id=1,
        owner_id=1,
        profile_key="deepseek-v4-flash",
        policy=policy,
        match_experience_fn=_fake_match_experience,
    )
    result = _rule_classify("某系统哪里看某功能？")

    matched = await runner._match_experiences("某系统哪里看某功能？", result)

    assert matched
    assert matched[0]["trigger_condition"] == "确认系统功能入口"


def test_parse_json_object_strips_markdown_fence() -> None:
    parsed = _parse_json_object('```json\n{"task_category":"creation"}\n```')

    assert parsed["task_category"] == "creation"


async def _fake_match_experience(query: str, limit: int, caller: str) -> list[dict]:
    if "系统" in query and ("功能" in query or "入口" in query or "页面" in query):
        return [{"id": 7, "trigger_condition": "确认系统功能入口", "steps": "[]"}]
    return []
