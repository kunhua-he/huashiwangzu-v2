"""Timing logs for knowledge-module LLM calls."""
from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Any

from .model_routing import knowledge_model_call_slot, record_model_rate_limit

ChatMessage = Mapping[str, str]
ChatFunc = Callable[..., Awaitable[dict[str, Any]]]

_RETRY_COUNT_NOTE = "unavailable_at_module_layer"


def _gateway_attempt_status(diagnostics: Mapping[str, Any]) -> tuple[bool, list[str]]:
    attempts = diagnostics.get("attempts")
    if not isinstance(attempts, Sequence) or isinstance(attempts, (str, bytes)):
        return False, []
    has_success = False
    errors: list[str] = []
    for attempt in attempts:
        if not isinstance(attempt, Mapping):
            continue
        if attempt.get("success") is True:
            has_success = True
            continue
        error = str(attempt.get("error") or "").strip()
        if error and error.lower() != "none":
            errors.append(error)
        else:
            errors.append("gateway attempt failed without error")
    return has_success, errors


def _message_chars(messages: Sequence[ChatMessage]) -> int:
    return sum(len(str(message.get("content") or "")) for message in messages)


def _user_chars(messages: Sequence[ChatMessage]) -> int:
    return sum(
        len(str(message.get("content") or ""))
        for message in messages
        if message.get("role") == "user"
    )


def _extra_text(extra: Mapping[str, object] | None) -> str:
    if not extra:
        return ""
    parts = [f"{key}={value}" for key, value in sorted(extra.items())]
    return " " + " ".join(parts)


def model_degradation_from_diagnostics(
    diagnostics: Mapping[str, Any] | None,
    requested_profile: str,
) -> dict[str, Any]:
    """Normalize gateway fallback diagnostics for knowledge stages."""
    diagnostics = diagnostics or {}
    selected_profile = str(diagnostics.get("selected_profile") or requested_profile)
    fallback_used = bool(diagnostics.get("fallback_used"))
    return {
        "requested_profile": requested_profile,
        "selected_profile": selected_profile,
        "selected_provider": str(diagnostics.get("selected_provider") or ""),
        "fallback_used": fallback_used,
        "model_degraded": fallback_used and selected_profile != requested_profile,
    }


def annotate_model_degradation(result: dict[str, Any], requested_profile: str) -> dict[str, Any]:
    """Attach normalized model fallback flags to a gateway result dict."""
    model_diagnostics = model_degradation_from_diagnostics(
        result.get("diagnostics") if isinstance(result.get("diagnostics"), Mapping) else None,
        requested_profile,
    )
    result["model_diagnostics"] = model_diagnostics
    result["model_degraded"] = bool(model_diagnostics["model_degraded"])
    return result


async def timed_llm_chat(
    *,
    logger: logging.Logger,
    stage: str,
    profile_key: str,
    messages: Sequence[ChatMessage],
    chat_func: ChatFunc,
    document_id: int | None = None,
    page: int | None = None,
    extra: Mapping[str, object] | None = None,
) -> dict[str, Any]:
    """Call the gateway chat function and emit structured timing logs."""
    input_chars = _message_chars(messages)
    user_chars = _user_chars(messages)
    extra_fields = _extra_text(extra)
    started = time.perf_counter()

    logger.info(
        "LLM_CALL_START stage=%s profile_key=%s document_id=%s page=%s "
        "input_chars=%d user_chars=%d retry_count=%s%s",
        stage,
        profile_key,
        document_id,
        page,
        input_chars,
        user_chars,
        _RETRY_COUNT_NOTE,
        extra_fields,
    )

    slot_info: Mapping[str, object] = {}
    try:
        async with knowledge_model_call_slot(stage) as acquired_slot:
            slot_info = acquired_slot
            result = await chat_func(messages=list(messages), profile_key=profile_key)
    except Exception as exc:
        pause_result = record_model_rate_limit(stage, error_message=exc)
        if pause_result.get("paused"):
            logger.error(
                "LLM_CALL_RATE_LIMIT_AUTO_PAUSE stage=%s group=%s count=%s threshold=%s paused_stages=%s",
                stage,
                pause_result.get("group"),
                pause_result.get("count"),
                pause_result.get("threshold"),
                pause_result.get("paused_stages"),
            )
        elapsed_ms = (time.perf_counter() - started) * 1000
        logger.warning(
            "LLM_CALL_ERROR stage=%s profile_key=%s document_id=%s page=%s "
            "elapsed_ms=%.1f input_chars=%d error_type=%s error=%s retry_count=%s%s "
            "model_slot_wait_ms=%s model_slot_limit=%s",
            stage,
            profile_key,
            document_id,
            page,
            elapsed_ms,
            input_chars,
            type(exc).__name__,
            exc,
            _RETRY_COUNT_NOTE,
            extra_fields,
            slot_info.get("wait_ms", ""),
            slot_info.get("limit", ""),
        )
        raise

    elapsed_ms = (time.perf_counter() - started) * 1000
    content = str(result.get("content") or "")
    annotate_model_degradation(result, profile_key)
    # Extract gateway diagnostics if present
    diagnostics = result.get("diagnostics") or {}
    has_gateway_success, gateway_attempt_errors = (
        _gateway_attempt_status(diagnostics) if isinstance(diagnostics, Mapping) else (False, [])
    )
    gateway_error_text = "\n".join(gateway_attempt_errors)
    if gateway_error_text:
        pause_result = record_model_rate_limit(stage, error_message=gateway_error_text)
        if pause_result.get("paused"):
            logger.error(
                "LLM_CALL_RATE_LIMIT_AUTO_PAUSE stage=%s group=%s count=%s threshold=%s paused_stages=%s",
                stage,
                pause_result.get("group"),
                pause_result.get("count"),
                pause_result.get("threshold"),
                pause_result.get("paused_stages"),
            )
        if (
            not has_gateway_success
            or pause_result.get("reason") not in {"not_rate_limit", "disabled", "not_model_stage"}
        ):
            raise RuntimeError(gateway_error_text)
    diag_fields = ""
    if diagnostics:
        trace_id = diagnostics.get("trace_id", "")
        attempts = diagnostics.get("attempts", 0)
        total_elapsed = diagnostics.get("total_elapsed_ms", 0)
        response_summary = diagnostics.get("response_summary", {})
        model_diagnostics = result.get("model_diagnostics") or {}
        diag_fields = (
            f" trace_id={trace_id} gateway_attempts={attempts}"
            f" gateway_elapsed_ms={total_elapsed}"
            f" output_chars={response_summary.get('output_chars', '')}"
            f" reasoning_chars={response_summary.get('reasoning_chars', '')}"
            f" selected_profile={model_diagnostics.get('selected_profile', '')}"
            f" model_degraded={model_diagnostics.get('model_degraded', False)}"
        )
    logger.info(
        "LLM_CALL_END stage=%s profile_key=%s document_id=%s page=%s "
        "elapsed_ms=%.1f input_chars=%d output_chars=%d tokens=%s ok=%s retry_count=%s%s "
        "model_slot_wait_ms=%s model_slot_limit=%s%s",
        stage,
        profile_key,
        document_id,
        page,
        elapsed_ms,
        input_chars,
        len(content),
        result.get("tokens"),
        bool(content.strip()),
        _RETRY_COUNT_NOTE,
        extra_fields,
        slot_info.get("wait_ms", ""),
        slot_info.get("limit", ""),
        diag_fields,
    )
    if result.get("model_degraded"):
        logger.warning(
            "LLM_CALL_DEGRADED stage=%s requested_profile=%s selected_profile=%s document_id=%s page=%s",
            stage,
            profile_key,
            result.get("model_diagnostics", {}).get("selected_profile"),
            document_id,
            page,
        )
    return result
