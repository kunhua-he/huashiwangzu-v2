"""Shortest-path trace summaries for Agent turns.

The runtime already records raw events, timelines, usage, trajectories, and
workflow ledgers.  This module folds those signals into a compact diagnostic
event that can drive prompt/recipe optimization without blocking the answer
path or hardcoding business content.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence

TRACE_SCHEMA_VERSION = 1
MAX_TOOL_STEPS = 12
MAX_TEXT = 500


def build_path_trace_summary(
    *,
    user_input: str,
    assistant_text: str,
    intent_preflight: Mapping[str, object] | None,
    route_diagnostics: Mapping[str, object] | None,
    tool_events: Sequence[Mapping[str, object]],
    timeline: Sequence[Mapping[str, object]],
    usage: Mapping[str, object] | None,
    message_id: int | None = None,
    sync_success_path_save_possible: bool = False,
) -> dict:
    """Build a compact per-turn path trace summary.

    The payload is intentionally diagnostic-only.  It answers:
    - what the turn was trying to do;
    - whether a previously mined shortcut was available;
    - which tool steps were taken and whether their outputs appear consumed;
    - what stopped the loop; and
    - whether automatic learning stayed on the async path.
    """
    intent = _intent_payload(intent_preflight)
    tool_steps = _tool_steps(tool_events, assistant_text)
    usage_payload = _usage_payload(usage)
    stop_condition = _stop_condition(
        assistant_text=assistant_text,
        tool_steps=tool_steps,
        timeline=timeline,
        usage=usage_payload,
    )
    result_usage = [step.get("result_usage") for step in tool_steps if step.get("type") == "tool"]
    unused_tool_result_count = sum(1 for item in result_usage if item == "unused")

    return {
        "schema_version": TRACE_SCHEMA_VERSION,
        "message_id": message_id,
        "user_input_preview": _clip(user_input, MAX_TEXT),
        "intent": intent,
        "recipe_match": _recipe_match_payload(route_diagnostics),
        "experience_match": _experience_payload(intent_preflight, route_diagnostics),
        "stop_condition": stop_condition,
        "tool_path": {
            "call_count": sum(1 for event in tool_events if event.get("type") == "tool_call"),
            "result_count": sum(1 for event in tool_events if event.get("type") == "tool_result"),
            "unique_tools": _unique_tools(tool_events),
            "steps": tool_steps,
            "unused_tool_result_count": unused_tool_result_count,
            "all_tools_successful": _all_tools_successful(tool_events),
        },
        "usage": usage_payload,
        "timeline": _timeline_payload(timeline),
        "learning": {
            "mode": "async",
            "post_turn_tasks": _planned_async_tasks(tool_events),
            "sync_success_path_save_possible": sync_success_path_save_possible,
        },
    }


def _intent_payload(intent_preflight: Mapping[str, object] | None) -> dict:
    source = intent_preflight or {}
    evidence = source.get("evidence_policy") if isinstance(source.get("evidence_policy"), Mapping) else {}
    risk = source.get("risk_policy") if isinstance(source.get("risk_policy"), Mapping) else {}
    return {
        "task_category": _str(source.get("task_category") or "unknown"),
        "answer_shape": _str(source.get("answer_shape") or "unknown"),
        "summary": _clip(_str(source.get("intent_summary") or ""), 300),
        "confidence": _number(source.get("confidence")),
        "domain_terms": _string_list(source.get("domain_terms")),
        "requires_citation": bool(risk.get("requires_citation")) if isinstance(risk, Mapping) else False,
        "needs_internal_knowledge": bool(evidence.get("needs_internal_knowledge")) if isinstance(evidence, Mapping) else False,
        "needs_external_web": bool(evidence.get("needs_external_web")) if isinstance(evidence, Mapping) else False,
    }


def _recipe_match_payload(route_diagnostics: Mapping[str, object] | None) -> dict:
    source = route_diagnostics or {}
    count = _int(source.get("recipe_injected"))
    labels = _string_list(source.get("recipe_labels"))
    return {
        "matched": count > 0,
        "count": count,
        "labels": labels,
    }


def _experience_payload(
    intent_preflight: Mapping[str, object] | None,
    route_diagnostics: Mapping[str, object] | None,
) -> dict:
    route = route_diagnostics or {}
    preflight = intent_preflight or {}
    injected = route.get("experience_injected")
    matched = preflight.get("matched_experiences")
    injected_ids = _string_list(injected)
    matched_count = len(matched) if isinstance(matched, Sequence) and not isinstance(matched, (str, bytes)) else 0
    return {
        "matched": bool(injected_ids or matched_count),
        "injected_ids": injected_ids,
        "matched_count": matched_count,
    }


def _tool_steps(events: Sequence[Mapping[str, object]], assistant_text: str) -> list[dict]:
    calls: list[Mapping[str, object]] = []
    results_by_id: dict[str, Mapping[str, object]] = {}
    sequential_results: list[Mapping[str, object]] = []

    for event in events:
        event_type = event.get("type")
        if event_type == "tool_call":
            calls.append(event)
        elif event_type == "tool_result":
            tool_call_id = _str(event.get("tool_call_id") or "")
            if tool_call_id:
                results_by_id[tool_call_id] = event
            else:
                sequential_results.append(event)

    steps: list[dict] = []
    seq_idx = 0
    for index, call in enumerate(calls[:MAX_TOOL_STEPS], start=1):
        tool_call_id = _str(call.get("tool_call_id") or call.get("id") or "")
        result = results_by_id.get(tool_call_id)
        if result is None and seq_idx < len(sequential_results):
            result = sequential_results[seq_idx]
            seq_idx += 1
        effective_name = _str(
            (result or {}).get("effective_tool_name")
            or call.get("effective_tool_name")
            or call.get("name")
        )
        args = call.get("arguments")
        if args is None:
            args = call.get("args")
        result_payload = result.get("result") if result else None
        refs = _result_reference_markers(result_payload)
        steps.append({
            "index": index,
            "type": "tool",
            "tool_name": _str(call.get("name") or ""),
            "effective_tool_name": effective_name,
            "tool_call_id": tool_call_id,
            "argument_keys": _dict_keys(args),
            "duration_ms": _number((result or {}).get("duration_ms")),
            "success": _tool_result_success(result_payload) if result else False,
            "has_result": result is not None,
            "result_reference_markers": refs[:6],
            "result_usage": _result_usage(refs, assistant_text),
        })

    if len(calls) > MAX_TOOL_STEPS:
        steps.append({
            "index": MAX_TOOL_STEPS + 1,
            "type": "truncated",
            "remaining_tool_calls": len(calls) - MAX_TOOL_STEPS,
        })
    return steps


def _stop_condition(
    *,
    assistant_text: str,
    tool_steps: Sequence[Mapping[str, object]],
    timeline: Sequence[Mapping[str, object]],
    usage: Mapping[str, object],
) -> dict:
    if not assistant_text.strip():
        reason = "empty_after_clean"
    elif any(item.get("type") == "contract_retry" and item.get("status") == "degraded" for item in timeline):
        reason = "tool_intent_degraded"
    elif any(step.get("type") == "truncated" for step in tool_steps):
        reason = "max_trace_steps_reached"
    elif tool_steps:
        reason = "final_answer_after_tools"
    else:
        reason = "direct_answer"
    return {
        "reason": reason,
        "model_call_count": _int(usage.get("model_call_count")),
        "answer_chars": len(assistant_text),
    }


def _usage_payload(usage: Mapping[str, object] | None) -> dict:
    source = usage or {}
    return {
        "prompt_tokens": _int(source.get("prompt_tokens")),
        "completion_tokens": _int(source.get("completion_tokens")),
        "total_tokens": _int(source.get("total_tokens")),
        "model_call_count": _int(source.get("model_call_count")),
        "max_single_call_prompt_tokens": _int(source.get("max_single_call_prompt_tokens")),
        "work_duration_ms": _int(source.get("work_duration_ms")),
    }


def _timeline_payload(timeline: Sequence[Mapping[str, object]]) -> dict:
    counts: dict[str, int] = {}
    for item in timeline:
        item_type = _str(item.get("type") or "unknown")
        counts[item_type] = counts.get(item_type, 0) + 1
    return {
        "event_count": len(timeline),
        "event_type_counts": counts,
    }


def _planned_async_tasks(tool_events: Sequence[Mapping[str, object]]) -> list[str]:
    tasks = ["memory_distill", "profile_evolve", "agent_context_compact"]
    if _has_query_context_id(tool_events):
        tasks.append("knowledge_retrieval_reflect")
    return tasks


def _unique_tools(events: Sequence[Mapping[str, object]]) -> list[str]:
    seen: set[str] = set()
    tools: list[str] = []
    for event in events:
        if event.get("type") != "tool_call":
            continue
        name = _str(event.get("name") or "")
        if name and name not in seen:
            seen.add(name)
            tools.append(name)
    return tools[:20]


def _all_tools_successful(events: Sequence[Mapping[str, object]]) -> bool:
    for event in events:
        if event.get("type") != "tool_result":
            continue
        if not _tool_result_success(event.get("result")):
            return False
    return True


def _tool_result_success(result: object) -> bool:
    if not isinstance(result, Mapping):
        return False
    if result.get("success") is False or result.get("error"):
        return False
    inner = result.get("data", result)
    if isinstance(inner, Mapping) and (inner.get("success") is False or inner.get("error")):
        return False
    if result.get("denied") or result.get("policy_blocked"):
        return False
    return True


def _result_reference_markers(result: object) -> list[str]:
    markers: list[str] = []
    seen: set[str] = set()

    def add(key: str, value: object) -> None:
        if len(markers) >= 20 or isinstance(value, (Mapping, list, tuple, set)) or value is None:
            return
        marker = f"{key}:{str(value).strip()}"
        if marker in seen or marker == f"{key}:":
            return
        seen.add(marker)
        markers.append(marker)

    def walk(node: object, depth: int = 0) -> None:
        if depth > 5 or len(markers) >= 20:
            return
        if isinstance(node, str):
            node = _parse_json_like(node)
        if isinstance(node, Mapping):
            for key, child in node.items():
                key_text = str(key)
                if key_text in {
                    "file_id", "source_file_id", "document_id", "chunk_id",
                    "package_id", "content_package_id", "query_context_id",
                    "record_id", "task_id", "url", "source", "document_name",
                    "filename", "title",
                }:
                    add(key_text, child)
                walk(child, depth + 1)
        elif isinstance(node, Sequence) and not isinstance(node, (str, bytes, bytearray)):
            for child in list(node)[:30]:
                walk(child, depth + 1)

    walk(result)
    return markers


def _result_usage(markers: Sequence[str], assistant_text: str) -> str:
    if not markers:
        return "unknown"
    normalized = assistant_text or ""
    for marker in markers:
        _, _, value = marker.partition(":")
        if value and value in normalized:
            return "used"
    return "unused"


def _has_query_context_id(events: Sequence[Mapping[str, object]]) -> bool:
    for event in events:
        if event.get("type") != "tool_result":
            continue
        if any(marker.startswith("query_context_id:") for marker in _result_reference_markers(event.get("result"))):
            return True
    return False


def _dict_keys(value: object) -> list[str]:
    value = _parse_json_like(value)
    if not isinstance(value, Mapping):
        return []
    return [str(key) for key in value.keys()][:20]


def _parse_json_like(value: object) -> object:
    if not isinstance(value, str):
        return value
    text = value.strip()
    if not text or text[0] not in "{[":
        return value
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return value


def _string_list(value: object) -> list[str]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_clip(_str(item), 120) for item in value if _str(item).strip()][:20]
    return []


def _number(value: object) -> int | float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int | float):
        return value
    try:
        number = float(str(value))
    except (TypeError, ValueError):
        return None
    return int(number) if number.is_integer() else number


def _int(value: object) -> int:
    number = _number(value)
    if isinstance(number, int | float):
        return int(number)
    return 0


def _str(value: object) -> str:
    return "" if value is None else str(value)


def _clip(text: str, limit: int) -> str:
    return text[:limit] if len(text) <= limit else text[:limit] + "...(truncated)"
