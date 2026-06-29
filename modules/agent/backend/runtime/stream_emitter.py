"""StreamEmitter — reusable SSE content streamer with inline-tool recovery.

Extracted from the old ``_yield_final_stream()`` in ``chat.py``.
Wraps the streaming model call, yields tokens to the frontend in
real-time while buffering a copy for inline XML tool call detection.

When inline tool calls are found after streaming, a ``replace`` SSE
event is sent to fix the already-displayed text, followed by a
``_inline_tool_calls`` dict signal for the caller to re-enter the tool loop.
"""

from __future__ import annotations

import json
import logging
import time

from ..engine.engine import chat_stream_with_degradation_chain
from ..engine.failure_diagnostics import record_failure
from .content_gate import TOOL_INTENT_RETRY_MESSAGE, looks_like_unfinished_tool_intent, user_safe_error_message

logger = logging.getLogger("v2.agent").getChild("runtime.stream_emitter")


class StreamEmitter:
    """Emit final-content SSE events, with inline tool-call recovery.

    Usage::

        emitter = StreamEmitter()
        async for event in emitter.yield_final_stream(messages, profile_key, ...):
            if isinstance(event, dict) and event.get("type") == "_inline_tool_calls":
                # caller should re-enter tool loop
                ...
            else:
                yield event   # raw bytes for StreamingResponse

    After the stream completes (no inline calls), ``emitter.usage_data``
    contains the token usage dict (prompt_tokens, completion_tokens,
    total_tokens), or ``None`` if unavailable.
    """

    def __init__(self) -> None:
        self.usage_data: dict | None = None

    async def yield_final_stream(
        self,
        messages: list[dict],
        profile_key: str = "deepseek-v4-flash",
        tools: list[dict] | None = None,
        conversation_id: int | None = None,
        owner_id: int | None = None,
        *,
        full_buffer: list[str] | None = None,
        thinking_buffer: list[str] | None = None,
        timeline: list[dict] | None = None,
        suppress_thinking: bool = False,
    ):
        """Stream final content — real-time SSE + buffered copy for inline detection.

        Yields ``bytes`` (SSE ``data: ...`` frames) for the frontend in
        real-time.  Also buffers all content in *full_buffer* for
        post-stream inline XML tool call detection.  If inline calls
        are found, yields a ``replace`` SSE event (to fix the
        already-displayed text) followed by a
        ``{"type": "_inline_tool_calls", ...}`` dict signal.

        Parameters mirror those of the old ``_yield_final_stream``.
        """
        logger.info("[DIAG] StreamEmitter.yield_final_stream ENTER")
        event_count = 0
        usage_event: bytes | None = None
        full = full_buffer if full_buffer is not None else []
        thinking_parts = thinking_buffer if thinking_buffer is not None else []
        tl = timeline if timeline is not None else []

        try:
            async for event in chat_stream_with_degradation_chain(
                messages, profile_key, tools,
                conversation_id=conversation_id,
            ):
                event_count += 1
                event_type = event.get("type")
                content = str(event.get("content") or "")
                logger.info(
                    "[DIAG] StreamEmitter event #%d type=%s content_len=%d",
                    event_count, event_type, len(content),
                )
                if event_type == "thinking" and content and not suppress_thinking:
                    from ..services.model_client import parse_inline_tool_calls
                    clean, _ = parse_inline_tool_calls(content)
                    thinking_parts.append(clean)
                    tl.append({"type": "thinking", "content": clean, "started_at": time.time()})
                    yield self._sse("thinking", clean)
                elif event_type in ("token", "content") and content:
                    full.append(content)
                    tl.append({"type": "text", "content": content, "started_at": time.time()})
                    # Real-time: yield token immediately to frontend
                    yield self._sse("token", content)
                elif event_type == "usage":
                    usage_data = event.get("data", {})
                    self.usage_data = usage_data
                    usage_event = self._sse("usage", json.dumps(usage_data, ensure_ascii=False))
                elif event_type == "error" and content:
                    logger.warning("StreamEmitter upstream model error: %s", content)
                    yield self._sse("error", user_safe_error_message(content))
                elif event_type == "done":
                    # DONE 可能携带 usage（DeepSeek adapter 嵌入在 DONE 中）
                    done_usage = event.get("usage")
                    if done_usage:
                        self.usage_data = done_usage
                        usage_event = self._sse("usage", json.dumps(done_usage, ensure_ascii=False))
                    logger.info(
                        "[DIAG] StreamEmitter got done event — stream ending",
                    )

            full_content = "".join(full)
            try:
                clean_content, inline_calls = parse_inline_tool_calls(full_content)
            except Exception as exc:
                logger.warning(
                    "StreamEmitter parse_inline_tool_calls failed: %s", exc,
                )
                clean_content, inline_calls = full_content, []

            if inline_calls:
                full.clear()
                full.append(clean_content)
                logger.info(
                    "[DIAG] StreamEmitter found %d inline tool calls, "
                    "re-entering tool loop", len(inline_calls),
                )
                # Tell frontend to replace streaming text with clean version
                yield self._sse("replace", json.dumps({"content": clean_content}, ensure_ascii=False))
                yield {"type": "_inline_tool_calls", "tool_calls": inline_calls}
                return

            if looks_like_unfinished_tool_intent(clean_content):
                full.clear()
                logger.warning(
                    "StreamEmitter requested retry for unfinished tool-intent reply: %s",
                    clean_content[:120],
                )
                yield self._sse("replace", json.dumps({"content": ""}, ensure_ascii=False))
                yield {
                    "type": "_retry_tool_intent_contract",
                    "content": clean_content,
                    "message": TOOL_INTENT_RETRY_MESSAGE,
                }
                return

            if usage_event:
                yield usage_event

            logger.info(
                "[DIAG] StreamEmitter EXIT after %d events — no inline calls",
                event_count,
            )
        except Exception as exc:
            logger.exception("StreamEmitter unexpected error: %s", exc)
            await record_failure(
                "chat", "yield_final_stream",
                type(exc).__name__, str(exc),
                conversation_id, owner_id,
            )
            yield self._sse(
                "error", user_safe_error_message(exc),
            )

    def assistant_stream_start(self, segment_id: str, message_id: int | None = None, role: str = "assistant") -> bytes:
        payload: dict = {"type": "assistant_stream_start", "segment_id": segment_id, "role": role}
        if message_id is not None:
            payload["message_id"] = message_id
        return self._json_sse(payload)

    def assistant_stream_delta(self, segment_id: str, text: str) -> bytes:
        return self._json_sse({"type": "assistant_stream_delta", "segment_id": segment_id, "content": text})

    def assistant_stream_rollback(self, segment_id: str, reason: str, replacement: str = "") -> bytes:
        return self._json_sse({
            "type": "assistant_stream_rollback",
            "segment_id": segment_id,
            "reason": reason,
            "replacement": replacement,
        })

    def assistant_stream_commit(self, segment_id: str, message_id: int | None = None, meta: dict | None = None) -> bytes:
        payload: dict = {"type": "assistant_stream_commit", "segment_id": segment_id}
        if message_id is not None:
            payload["message_id"] = message_id
        if meta:
            payload["meta"] = meta
        return self._json_sse(payload)

    @staticmethod
    def _json_sse(payload: dict) -> bytes:
        return (
            f"data: {json.dumps(payload, ensure_ascii=False, default=str)}\n\n"
        ).encode("utf-8")

    @staticmethod
    def _sse(event_type: str, content: str) -> bytes:
        """Format a single SSE ``data:`` frame."""
        return (
            f"data: {json.dumps({'type': event_type, 'content': content}, ensure_ascii=False)}\n\n"
        ).encode("utf-8")
