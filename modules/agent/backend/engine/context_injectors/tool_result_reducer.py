"""Tool result reducer: compress large tool outputs before they enter the model context.

Strategy:
- JSON content > MAX_JSON_CHARS: compress to head/tail with truncation marker
- Text content > MAX_TEXT_CHARS: head/tail truncation
- list_files/search results: keep first N items + total count
- General fallback: keep head 30% + tail 20%

This is a pure function: takes projected messages, returns compressed copies.
Does NOT modify the event store - the original data is preserved in agent_events.
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger("v2.agent").getChild("reducer.tool_result")

# ── Default limits (configurable per profile later) ──
_MAX_JSON_CHARS = 2000
_MAX_TEXT_CHARS = 3000
_MAX_LIST_ITEMS = 15
_MAX_HEAD_PERCENT = 0.30
_MAX_TAIL_PERCENT = 0.20


def is_json_content(text: str) -> bool:
    """Check if the text looks like a JSON payload."""
    text = text.strip()
    return text.startswith("{") or text.startswith("[")


def _truncate_json(payload: str, max_chars: int = _MAX_JSON_CHARS) -> str:
    """Compress a JSON payload by keeping key structure and truncating arrays/values."""
    if len(payload) <= max_chars:
        return payload
    try:
        data = json.loads(payload)
    except (json.JSONDecodeError, ValueError):
        return _truncate_text_heuristic(payload, max_chars)

    compressed = _compress_json_value(data)
    result = json.dumps(compressed, ensure_ascii=False)
    if len(result) <= max_chars:
        return result
    return _truncate_text_heuristic(payload, max_chars)


def _compress_json_value(value: Any, depth: int = 0) -> Any:
    """Recursively compress a JSON value."""
    if depth > 3:  # limit recursion depth
        return "[…]" if isinstance(value, (dict, list)) else value

    if isinstance(value, dict):
        compressed: dict[str, Any] = {}
        for k, v in value.items():
            if isinstance(v, str) and len(v) > 200:
                compressed[k] = v[:120] + "…" + v[-60:]
            elif isinstance(v, list) and len(v) > _MAX_LIST_ITEMS:
                compressed[k] = _compress_json_value(v[: _MAX_LIST_ITEMS], depth + 1)
                compressed[f"{k}_total"] = len(v)
            else:
                compressed[k] = _compress_json_value(v, depth + 1)
        return compressed
    if isinstance(value, list):
        truncated = []
        for item in value:
            truncated.append(_compress_json_value(item, depth + 1))
            if len(truncated) >= _MAX_LIST_ITEMS:
                break
        truncated.append(f"…{len(value)} items total")
        return truncated
    return value


def _truncate_text_heuristic(text: str, max_chars: int = _MAX_TEXT_CHARS) -> str:
    """Compress long text by keeping head and tail."""
    if len(text) <= max_chars:
        return text
    head_len = int(max_chars * _MAX_HEAD_PERCENT)
    tail_len = int(max_chars * _MAX_TAIL_PERCENT)
    tail_len = max(tail_len, min(200, max_chars // 4))
    head = text[:head_len]
    tail = text[-tail_len:]
    return f"{head}\n\n[内容截断：省略 {len(text) - head_len - tail_len} 字符]\n\n{tail}"


def _reduce_tool_content(content: str, tool_name: str = "") -> str:
    """Apply tool-specific compression rules based on content shape and tool name."""
    if not content or len(content) < 500:
        return content

    # JSON content: structured compression
    if is_json_content(content):
        return _truncate_json(content)

    # Text content: head/tail
    return _truncate_text_heuristic(content)


def reduce(
    projected_messages: list[dict],
    max_json_chars: int = _MAX_JSON_CHARS,
    max_text_chars: int = _MAX_TEXT_CHARS,
) -> tuple[list[dict], dict]:
    """Compress tool results in projected messages.

    Args:
        projected_messages: list of model messages (from project_to_messages)
        max_json_chars: max chars before JSON compression
        max_text_chars: max chars before text truncation

    Returns:
        (reduced_messages, diagnosis)
        diagnosis contains counts of which messages were compressed.
    """
    reduced = list(projected_messages)
    compressed_count = 0
    compressed_chars = 0

    for i, msg in enumerate(reduced):
        if msg.get("role") != "tool":
            continue
        content = msg.get("content", "")
        if not content or not isinstance(content, str):
            continue

        original_len = len(content)
        tool_name = msg.get("name", "")
        reduced_content = _reduce_tool_content(content, tool_name)

        if len(reduced_content) < original_len:
            reduced[i] = dict(msg, content=reduced_content)
            compressed_count += 1
            compressed_chars += original_len - len(reduced_content)

    diagnosis: dict[str, Any] = {
        "tool_results_compressed": compressed_count,
        "total_chars_saved": compressed_chars,
        "total_messages": len(projected_messages),
    }
    return reduced, diagnosis
