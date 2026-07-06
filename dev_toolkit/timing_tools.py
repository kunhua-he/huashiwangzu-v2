"""Helpers for machine-readable verification timing summaries."""

from __future__ import annotations

import json
from typing import Any

TOOL_COMPONENT = False


def _string_value(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text or default


def _float_value(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return round(float(value), 3)
    except (TypeError, ValueError):
        return None


def normalize_timing_item(item: Any, index: int = 0) -> tuple[dict[str, Any] | None, str | None]:
    if not isinstance(item, dict):
        return None, f"timing item {index} ignored: expected object"

    name = _string_value(
        item.get("name")
        or item.get("tool")
        or item.get("target")
        or item.get("command"),
        f"timing_{index + 1}",
    )
    duration = _float_value(
        item.get("duration_seconds")
        if "duration_seconds" in item
        else item.get("duration") if "duration" in item else item.get("seconds")
    )
    status = item.get("status")
    if status is None and "success" in item:
        status = "pass" if bool(item.get("success")) else "fail"

    normalized = {
        "name": name,
        "status": _string_value(status, "unknown"),
        "duration_seconds": duration,
    }
    for key in ("command", "level", "source"):
        if item.get(key) is not None:
            normalized[key] = _string_value(item.get(key))
    return normalized, None


def summarize_timing_items(items: list[dict[str, Any]]) -> dict[str, Any]:
    durations = [item["duration_seconds"] for item in items if isinstance(item.get("duration_seconds"), int | float)]
    return {
        "count": len(items),
        "timed_count": len(durations),
        "total_duration_seconds": round(sum(durations), 3),
    }


def parse_timing_data(raw: str = "") -> dict[str, Any]:
    text = (raw or "").strip()
    timing: dict[str, Any] = {"items": [], "summary": summarize_timing_items([]), "warnings": []}
    if not text:
        return timing

    try:
        decoded = json.loads(text)
    except json.JSONDecodeError as exc:
        timing["warnings"].append(f"timing_data ignored: invalid JSON at char {exc.pos}")
        return timing

    if isinstance(decoded, dict):
        raw_items = decoded.get("items") or decoded.get("timings") or decoded.get("tests")
        if raw_items is None:
            raw_items = [decoded]
    elif isinstance(decoded, list):
        raw_items = decoded
    else:
        timing["warnings"].append("timing_data ignored: expected JSON array or object")
        return timing

    if not isinstance(raw_items, list):
        timing["warnings"].append("timing_data ignored: items/timings/tests must be a list")
        return timing

    for index, item in enumerate(raw_items):
        normalized, warning = normalize_timing_item(item, index)
        if warning:
            timing["warnings"].append(warning)
            continue
        if normalized is not None:
            timing["items"].append(normalized)
    timing["summary"] = summarize_timing_items(timing["items"])
    return timing


def append_timing_item(timing: dict[str, Any], item: dict[str, Any]) -> None:
    normalized, warning = normalize_timing_item(item, len(timing.get("items", [])))
    timing.setdefault("items", [])
    timing.setdefault("warnings", [])
    if warning:
        timing["warnings"].append(warning)
    elif normalized is not None:
        timing["items"].append(normalized)
    timing["summary"] = summarize_timing_items(timing["items"])
