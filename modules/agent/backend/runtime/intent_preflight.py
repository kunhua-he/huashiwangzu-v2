from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from typing import Awaitable, Callable

from app.database import AsyncSessionLocal
from app.gateway import service as gateway_service

from ..engine.experience_memory import match_experience
from ..prompt_seeds import INTENT_PREFLIGHT_KEY
from ..services.runtime_prompt_provider import RuntimePromptProvider
from .runtime_policy import RuntimePolicy

logger = logging.getLogger("v2.agent").getChild("runtime.intent_preflight")

ChatFn = Callable[[list[dict], str], Awaitable[dict]]
MatchExperienceFn = Callable[[str, int, str], Awaitable[list[dict]]]

EVIDENCE_SENSITIVE_SHAPES = {
    "menu_path",
    "exact_number",
    "legal_or_policy_claim",
    "source_dependent_fact",
}

_SMALLTALK_RE = re.compile(r"^(hi|hello|你好|在吗|谢谢|再见|bye|ok|好的)[。！？!?.\s]*$", re.I)
_CREATION_RE = re.compile(r"写|改写|润色|生成|起草|文案|标题|脚本|邮件|方案文案")
_EXTERNAL_RE = re.compile(r"最新|新闻|官网|网上|联网|查一下|搜索|外部|公开资料|行情|今天|现在")
_INTERNAL_RE = re.compile(r"公司|内部|产品|品牌|成分|规格|制度|流程|知识库|企业")
_OPERATION_RE = re.compile(r"在哪|哪里|哪个页面|什么页面|入口|菜单|后台|路径|怎么打开|怎么看|查看")
_TROUBLESHOOT_RE = re.compile(r"报错|失败|不生效|异常|卡住|打不开|崩溃|修复|排查")
_CODING_RE = re.compile(r"代码|函数|接口|类|bug|堆栈|traceback|typescript|python|sql|api")
_DOCUMENT_RE = re.compile(r"文件|文档|表格|pdf|word|excel|docx|xlsx|ppt|总结这个|分析这份")
_SUMMARY_RE = re.compile(r"总结|归纳|提炼|概括|摘要")
_CLARIFY_ONLY_RE = re.compile(r"^(帮我弄一下|处理一下|搞一下|看一下|帮我看看)[。！？!?.\s]*$")


@dataclass
class EvidencePolicy:
    prefer_success_experience: bool = True
    needs_internal_knowledge: bool = False
    needs_external_web: bool = False
    needs_file_context: bool = False
    can_answer_from_general_knowledge: bool = True
    should_ask_clarification: bool = False


@dataclass
class ToolStrategy:
    first_actions: list[str] = field(default_factory=list)
    avoid_actions: list[str] = field(default_factory=list)
    suggested_queries: list[str] = field(default_factory=list)


@dataclass
class RiskPolicy:
    hallucination_risk: str = "low"
    requires_citation: bool = False
    must_not_overclaim: bool = False
    if_no_evidence: str = "answer_with_caveat"


@dataclass
class IntentPreflightResult:
    intent_summary: str = ""
    task_category: str = "other"
    answer_shape: str = "direct_answer"
    domain_terms: list[str] = field(default_factory=list)
    known_constraints: list[str] = field(default_factory=list)
    missing_slots: list[str] = field(default_factory=list)
    confidence: float = 0.0
    evidence_policy: EvidencePolicy = field(default_factory=EvidencePolicy)
    tool_strategy: ToolStrategy = field(default_factory=ToolStrategy)
    risk_policy: RiskPolicy = field(default_factory=RiskPolicy)
    matched_experiences: list[dict] = field(default_factory=list)
    verifier: dict = field(default_factory=dict)
    usage: dict = field(default_factory=dict)
    triggered: bool = True
    error: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class IntentPreflightRunner:
    """Rule-first advisory router before the tool loop.

    This layer is intentionally lightweight and non-blocking by default.  It
    derives generic task/evidence hints from deterministic text-shape rules,
    then lets the main model/tool loop do the real work under deterministic
    gates.  LLM classification is an optional fallback only.
    """

    def __init__(
        self,
        conversation_id: int,
        owner_id: int,
        profile_key: str,
        policy: RuntimePolicy,
        *,
        chat_fn: ChatFn | None = None,
        match_experience_fn: MatchExperienceFn | None = None,
    ) -> None:
        self.conversation_id = conversation_id
        self.owner_id = owner_id
        self.profile_key = profile_key
        self.policy = policy
        self._chat_fn = chat_fn or self._default_chat
        self._match_experience_fn = match_experience_fn or self._default_match_experience

    async def run(self, user_input: str) -> IntentPreflightResult:
        if not self.policy.intent_preflight_enabled:
            return IntentPreflightResult(triggered=False)
        try:
            result = _rule_classify(user_input)
            if _should_use_llm_fallback(result, self.policy):
                result = await self._classify_with_llm(user_input)
            result.matched_experiences = await self._match_experiences(user_input, result)
            return result
        except Exception as exc:
            logger.warning("Intent preflight failed (non-fatal): %s", exc)
            return IntentPreflightResult(error=str(exc))

    async def build_injection(self, result: IntentPreflightResult) -> str:
        if not result.triggered or result.error:
            return ""
        if result.task_category in {"smalltalk", "creation"} and not result.matched_experiences:
            return ""
        hints = [
            f"任务类型：{result.task_category}",
            f"答案形态：{result.answer_shape}",
        ]
        if result.tool_strategy.first_actions:
            hints.append("建议动作：" + " → ".join(result.tool_strategy.first_actions[:4]))
        if result.risk_policy.must_not_overclaim:
            hints.append("边界：无证据时避免过度断言，可带不确定性说明。")
        if result.matched_experiences:
            hints.append("已命中成功经验，若不冲突可优先参考。")
        return "\n\n---\n\n【本轮路由提示】" + "；".join(hints)

    async def _classify_with_llm(self, user_input: str) -> IntentPreflightResult:
        async with AsyncSessionLocal() as db:
            prompt = await RuntimePromptProvider(db).get_system_prompt(INTENT_PREFLIGHT_KEY)
        response = await self._chat_fn(
            [
                {"role": "system", "content": prompt},
                {"role": "user", "content": user_input},
            ],
            self.profile_key,
        )
        parsed = _parse_json_object(str(response.get("content") or ""))
        result = _result_from_payload(parsed)
        _accumulate_usage(result.usage, response.get("usage"))
        return result

    async def _match_experiences(self, user_input: str, result: IntentPreflightResult) -> list[dict]:
        queries = _dedupe_texts([
            user_input,
            result.intent_summary,
            " ".join([result.task_category, result.answer_shape, *result.domain_terms]),
            *result.tool_strategy.suggested_queries[:2],
        ])
        matched: list[dict] = []
        seen: set[str] = set()
        caller = f"user:{self.owner_id}" if self.owner_id else "system:agent"
        for query in queries[:4]:
            for item in await self._match_experience_fn(query, 2, caller):
                key = str(item.get("id") or item.get("trigger_condition") or item)
                if key in seen:
                    continue
                seen.add(key)
                matched.append(item)
                if len(matched) >= 3:
                    return matched
        return matched

    async def _needs_verifier(self, result: IntentPreflightResult) -> bool:
        return bool(self.policy.intent_preflight_use_verifier and self.policy.intent_preflight_max_llm_calls >= 2)

    async def _default_chat(self, messages: list[dict], profile_key: str) -> dict:
        return await gateway_service.chat(messages=messages, profile_key=profile_key)

    async def _default_match_experience(self, query: str, limit: int, caller: str) -> list[dict]:
        return await match_experience(query=query, limit=limit, caller=caller)


def _rule_classify(user_input: str) -> IntentPreflightResult:
    text = user_input.strip()
    terms = _extract_domain_terms(text)
    if not text or _CLARIFY_ONLY_RE.search(text):
        return IntentPreflightResult(
            intent_summary="用户请求缺少可执行对象",
            task_category="other",
            answer_shape="clarification",
            missing_slots=["具体对象", "要完成的动作"],
            confidence=0.9,
            evidence_policy=EvidencePolicy(should_ask_clarification=True, can_answer_from_general_knowledge=False),
            tool_strategy=ToolStrategy(first_actions=["clarify"]),
            risk_policy=RiskPolicy(hallucination_risk="medium", must_not_overclaim=True, if_no_evidence="ask_clarification"),
        )
    if _SMALLTALK_RE.search(text):
        return IntentPreflightResult("普通寒暄", "smalltalk", "direct_answer", terms, confidence=0.95)
    if _CREATION_RE.search(text):
        return IntentPreflightResult(
            "用户需要生成或改写内容",
            "creation",
            "direct_answer",
            terms,
            confidence=0.85,
            tool_strategy=ToolStrategy(first_actions=["direct_answer"]),
        )
    if _DOCUMENT_RE.search(text):
        return IntentPreflightResult(
            "用户的问题可能需要文件或文档上下文",
            "document_analysis",
            "summary",
            terms,
            confidence=0.8,
            evidence_policy=EvidencePolicy(needs_file_context=True, can_answer_from_general_knowledge=False),
            tool_strategy=ToolStrategy(first_actions=["file_context", "direct_answer"], suggested_queries=_queries(text, terms)),
            risk_policy=RiskPolicy(hallucination_risk="medium", requires_citation=True, must_not_overclaim=True),
        )
    if _CODING_RE.search(text):
        return IntentPreflightResult(
            "用户需要代码或技术问题处理",
            "coding",
            "code",
            terms,
            confidence=0.8,
            tool_strategy=ToolStrategy(first_actions=["direct_answer"]),
        )
    if _TROUBLESHOOT_RE.search(text):
        return IntentPreflightResult(
            "用户需要排查异常或失败原因",
            "troubleshooting",
            "plan",
            terms,
            confidence=0.78,
            tool_strategy=ToolStrategy(first_actions=["direct_answer", "clarify"]),
            risk_policy=RiskPolicy(hallucination_risk="medium", must_not_overclaim=True),
        )
    if _EXTERNAL_RE.search(text):
        return IntentPreflightResult(
            "用户需要公开或实时信息",
            "external_research",
            "source_dependent_fact",
            terms,
            confidence=0.82,
            evidence_policy=EvidencePolicy(needs_external_web=True, can_answer_from_general_knowledge=False),
            tool_strategy=ToolStrategy(first_actions=["external_research", "answer_with_caveat"], suggested_queries=_queries(text, terms)),
            risk_policy=RiskPolicy(hallucination_risk="medium", requires_citation=True, must_not_overclaim=True, if_no_evidence="search_more"),
        )
    if _OPERATION_RE.search(text):
        return IntentPreflightResult(
            "用户想确认某个系统或流程中的入口/页面/操作路径",
            "operation_path",
            "menu_path",
            terms,
            confidence=0.78,
            evidence_policy=EvidencePolicy(needs_internal_knowledge=True, needs_external_web=True, can_answer_from_general_knowledge=True),
            tool_strategy=ToolStrategy(
                first_actions=["match_experience", "internal_retrieval", "external_research", "answer_with_caveat"],
                avoid_actions=["do_not_overclaim_specific_paths_without_evidence"],
                suggested_queries=_queries(text, terms),
            ),
            risk_policy=RiskPolicy(hallucination_risk="medium", requires_citation=False, must_not_overclaim=True, if_no_evidence="answer_with_caveat"),
        )
    if _INTERNAL_RE.search(text):
        return IntentPreflightResult(
            "用户需要内部知识或企业资料",
            "internal_knowledge",
            "fact",
            terms,
            confidence=0.8,
            evidence_policy=EvidencePolicy(needs_internal_knowledge=True, can_answer_from_general_knowledge=False),
            tool_strategy=ToolStrategy(first_actions=["match_experience", "internal_retrieval"], suggested_queries=_queries(text, terms)),
            risk_policy=RiskPolicy(hallucination_risk="medium", requires_citation=True, must_not_overclaim=True, if_no_evidence="say_uncertain"),
        )
    if _SUMMARY_RE.search(text):
        return IntentPreflightResult(
            "用户需要总结或提炼信息",
            "creation",
            "summary",
            terms,
            confidence=0.75,
            tool_strategy=ToolStrategy(first_actions=["direct_answer"]),
        )
    return IntentPreflightResult(
        intent_summary="普通可回答问题",
        task_category="factual_lookup" if "?" in text or "？" in text else "other",
        answer_shape="direct_answer",
        domain_terms=terms,
        confidence=0.65,
        tool_strategy=ToolStrategy(first_actions=["direct_answer", "answer_with_caveat"], suggested_queries=_queries(text, terms)),
    )


def _should_use_llm_fallback(result: IntentPreflightResult, policy: RuntimePolicy) -> bool:
    if policy.intent_preflight_max_llm_calls <= 0:
        return False
    if policy.intent_preflight_mode not in {"rules_with_llm_fallback", "llm"}:
        return False
    if policy.intent_preflight_mode == "llm":
        return True
    return result.task_category in {"other"} and result.confidence < policy.intent_preflight_min_confidence


def _extract_domain_terms(text: str) -> list[str]:
    tokens = re.findall(r"[\u4e00-\u9fffA-Za-z0-9_-]{2,}", text)
    stop = {"哪个", "什么", "可以", "看到", "一下", "这个", "那个", "怎么", "哪里", "在哪"}
    return [tok for tok in tokens if tok not in stop][:8]


def _queries(text: str, terms: list[str]) -> list[str]:
    compact = " ".join(terms[:6]) or text[:80]
    return [compact] if compact else []


def _accumulate_usage(target: dict, usage: object) -> None:
    if not isinstance(usage, dict):
        return
    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
        value = usage.get(key, 0)
        if isinstance(value, (int, float)):
            target[key] = int(target.get(key, 0) or 0) + int(value)


def _parse_json_object(content: str) -> dict:
    text = content.strip()
    if not text:
        return {}
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                data = json.loads(text[start:end + 1])
                return data if isinstance(data, dict) else {}
            except json.JSONDecodeError:
                return {}
    return {}


def _result_from_payload(payload: dict) -> IntentPreflightResult:
    evidence = payload.get("evidence_policy") if isinstance(payload.get("evidence_policy"), dict) else {}
    strategy = payload.get("tool_strategy") if isinstance(payload.get("tool_strategy"), dict) else {}
    risk = payload.get("risk_policy") if isinstance(payload.get("risk_policy"), dict) else {}
    return IntentPreflightResult(
        intent_summary=str(payload.get("intent_summary") or ""),
        task_category=_enum_value(payload.get("task_category"), "other"),
        answer_shape=_enum_value(payload.get("answer_shape"), "direct_answer"),
        domain_terms=_string_list(payload.get("domain_terms")),
        known_constraints=_string_list(payload.get("known_constraints")),
        missing_slots=_string_list(payload.get("missing_slots")),
        confidence=_float_between(payload.get("confidence"), 0.0, 1.0),
        evidence_policy=EvidencePolicy(
            prefer_success_experience=bool(evidence.get("prefer_success_experience", True)),
            needs_internal_knowledge=bool(evidence.get("needs_internal_knowledge", False)),
            needs_external_web=bool(evidence.get("needs_external_web", False)),
            needs_file_context=bool(evidence.get("needs_file_context", False)),
            can_answer_from_general_knowledge=bool(evidence.get("can_answer_from_general_knowledge", True)),
            should_ask_clarification=bool(evidence.get("should_ask_clarification", False)),
        ),
        tool_strategy=ToolStrategy(
            first_actions=_string_list(strategy.get("first_actions")),
            avoid_actions=_string_list(strategy.get("avoid_actions")),
            suggested_queries=_string_list(strategy.get("suggested_queries")),
        ),
        risk_policy=RiskPolicy(
            hallucination_risk=_enum_value(risk.get("hallucination_risk"), "medium"),
            requires_citation=bool(risk.get("requires_citation", False)),
            must_not_overclaim=bool(risk.get("must_not_overclaim", True)),
            if_no_evidence=_enum_value(risk.get("if_no_evidence"), "answer_with_caveat"),
        ),
    )


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()][:8]


def _dedupe_texts(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        normalized = value.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        out.append(normalized)
    return out


def _float_between(value: object, low: float, high: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return low
    return min(high, max(low, number))


def _enum_value(value: object, default: str) -> str:
    text = str(value or "").strip()
    return text or default
