from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from typing import Awaitable, Callable

from app.database import AsyncSessionLocal
from app.gateway import service as gateway_service

from ..prompt_seeds import INTENT_PREFLIGHT_KEY
from ..services.runtime_prompt_provider import RuntimePromptProvider
from .runtime_policy import RuntimePolicy

logger = logging.getLogger("v2.agent").getChild("runtime.intent_preflight")

ChatFn = Callable[[list[dict], str], Awaitable[dict]]

EVIDENCE_SENSITIVE_SHAPES = {
    "menu_path",
    "exact_number",
    "legal_or_policy_claim",
    "source_dependent_fact",
}

_SMALLTALK_RE = re.compile(r"^(hi|hello|你好|在吗|谢谢|再见|bye|ok|好的)[。！？!?.\s]*$", re.I)
_CREATION_RE = re.compile(r"写|改写|润色|生成|起草|文案|标题|脚本|邮件|方案文案")
_EXTERNAL_RE = re.compile(r"最新|新闻|官网|网上|联网|查一下|搜索|外部|公开资料|行情|今天|现在")
_INTERNAL_RE = re.compile(r"公司|内部|企业|组织|团队|私有|知识库|制度|流程")
_OPERATION_RE = re.compile(r"在哪|哪里|哪个页面|什么页面|入口|菜单|后台|路径|怎么打开|怎么看|查看")
_TROUBLESHOOT_RE = re.compile(r"报错|失败|不生效|异常|卡住|打不开|崩溃|修复|排查")
_CODING_RE = re.compile(r"代码|函数|接口|类|bug|堆栈|traceback|typescript|python|sql|api")
_DOCUMENT_RE = re.compile(r"文件|文档|表格|pdf|word|excel|docx|xlsx|ppt|总结这个|分析这份")
_SUMMARY_RE = re.compile(r"总结|归纳|提炼|概括|摘要")
_CLARIFY_ONLY_RE = re.compile(r"^(帮我弄一下|处理一下|搞一下|看一下|帮我看看)[。！？!?.\s]*$")


@dataclass
class EvidencePolicy:
    needs_internal_knowledge: bool = False
    needs_external_web: bool = False
    needs_file_context: bool = False
    can_answer_from_general_knowledge: bool = True
    should_ask_clarification: bool = False


@dataclass
class ToolStrategy:
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
    ) -> None:
        self.conversation_id = conversation_id
        self.owner_id = owner_id
        self.profile_key = profile_key
        self.policy = policy
        self._chat_fn = chat_fn or self._default_chat

    async def run(self, user_input: str) -> IntentPreflightResult:
        if not self.policy.intent_preflight_enabled:
            return IntentPreflightResult(triggered=False)
        try:
            result = _rule_classify(user_input)
            if _should_use_llm_fallback(result, self.policy):
                result = await self._classify_with_llm(user_input)
            return result
        except Exception as exc:
            logger.warning("Intent preflight failed (non-fatal): %s", exc)
            return IntentPreflightResult(error=str(exc))

    async def build_injection(self, result: IntentPreflightResult) -> str:
        if not result.triggered or result.error:
            return ""
        if result.task_category in {"smalltalk", "creation"}:
            return ""
        hints = [
            f"任务类型：{result.task_category}",
            f"答案形态：{result.answer_shape}",
        ]
        stop_hint = _stop_condition_hint(result)
        if stop_hint:
            hints.append("停止条件：" + stop_hint)
        avoid_hint = _avoid_redundant_exploration_hint(result)
        if avoid_hint:
            hints.append("避免：" + avoid_hint)
        if result.risk_policy.must_not_overclaim:
            hints.append("边界：无证据时避免过度断言，可带不确定性说明。")
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

    async def _needs_verifier(self, result: IntentPreflightResult) -> bool:
        return bool(self.policy.intent_preflight_use_verifier and self.policy.intent_preflight_max_llm_calls >= 2)

    async def _default_chat(self, messages: list[dict], profile_key: str) -> dict:
        return await gateway_service.chat(messages=messages, profile_key=profile_key)


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
        )
    if _DOCUMENT_RE.search(text):
        return IntentPreflightResult(
            "用户的问题可能需要文件或文档上下文",
            "document_analysis",
            "summary",
            terms,
            confidence=0.8,
            evidence_policy=EvidencePolicy(needs_file_context=True, can_answer_from_general_knowledge=False),
            tool_strategy=ToolStrategy(suggested_queries=_queries(text, terms)),
            risk_policy=RiskPolicy(hallucination_risk="medium", requires_citation=True, must_not_overclaim=True),
        )
    if _CODING_RE.search(text):
        return IntentPreflightResult(
            "用户需要代码或技术问题处理",
            "coding",
            "code",
            terms,
            confidence=0.8,
        )
    if _TROUBLESHOOT_RE.search(text):
        return IntentPreflightResult(
            "用户需要排查异常或失败原因",
            "troubleshooting",
            "plan",
            terms,
            confidence=0.78,
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
            tool_strategy=ToolStrategy(suggested_queries=_queries(text, terms)),
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
            tool_strategy=ToolStrategy(suggested_queries=_queries(text, terms)),
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
            tool_strategy=ToolStrategy(suggested_queries=_queries(text, terms)),
            risk_policy=RiskPolicy(hallucination_risk="medium", requires_citation=True, must_not_overclaim=True, if_no_evidence="say_uncertain"),
        )
    if _SUMMARY_RE.search(text):
        return IntentPreflightResult(
            "用户需要总结或提炼信息",
            "creation",
            "summary",
            terms,
            confidence=0.75,
        )
    return IntentPreflightResult(
        intent_summary="普通可回答问题",
        task_category="factual_lookup" if "?" in text or "？" in text else "other",
        answer_shape="direct_answer",
        domain_terms=terms,
        confidence=0.65,
        tool_strategy=ToolStrategy(suggested_queries=_queries(text, terms)),
    )


def _should_use_llm_fallback(result: IntentPreflightResult, policy: RuntimePolicy) -> bool:
    if policy.intent_preflight_max_llm_calls <= 0:
        return False
    if policy.intent_preflight_mode not in {"rules_with_llm_fallback", "llm"}:
        return False
    if policy.intent_preflight_mode == "llm":
        return True
    return result.task_category in {"other"} and result.confidence < policy.intent_preflight_min_confidence


def _stop_condition_hint(result: IntentPreflightResult) -> str:
    """Return a concise, generic stop condition for this route."""
    evidence = result.evidence_policy
    if result.answer_shape == "clarification":
        return "缺少必要输入时先问清楚，不进入工具探索。"
    if evidence.needs_internal_knowledge:
        return (
            "已有与请求相关的证据结果，且能覆盖答案形态时，立即基于证据回答；"
            "需要来源时保留引用，不继续做锦上添花探索。"
        )
    if evidence.needs_file_context:
        return "文件内容已覆盖用户要求的范围时立即总结或回答，不重复读取同一材料。"
    if evidence.needs_external_web:
        return "已有足够公开来源支持核心结论时立即回答并列出来源，不为同一未知点反复搜索。"
    return "当前未知点已被验证且可以形成答案时立即回答。"


def _avoid_redundant_exploration_hint(result: IntentPreflightResult) -> str:
    if result.risk_policy.must_not_overclaim:
        return "没有足够证据时不要断言具体事实、入口或路径"
    return ""


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
            needs_internal_knowledge=bool(evidence.get("needs_internal_knowledge", False)),
            needs_external_web=bool(evidence.get("needs_external_web", False)),
            needs_file_context=bool(evidence.get("needs_file_context", False)),
            can_answer_from_general_knowledge=bool(evidence.get("can_answer_from_general_knowledge", True)),
            should_ask_clarification=bool(evidence.get("should_ask_clarification", False)),
        ),
        tool_strategy=ToolStrategy(
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


def _float_between(value: object, low: float, high: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return low
    return min(high, max(low, number))


def _enum_value(value: object, default: str) -> str:
    text = str(value or "").strip()
    return text or default
