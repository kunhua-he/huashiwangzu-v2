"""Shared semantic-failure helpers for dev toolkit checks."""

from __future__ import annotations

import json
from typing import Any


def _non_empty_error(value: Any) -> str | None:
    if value in (None, ""):
        return None
    if isinstance(value, str):
        text = value.strip()
        return text or None
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    except TypeError:
        return str(value)


def _legacy_code_failure(value: Any) -> bool:
    if value in (None, "", 0, "0"):
        return False
    if isinstance(value, bool):
        return value is not False
    if isinstance(value, int | float):
        return value != 0
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return False
        try:
            return float(text) != 0
        except ValueError:
            return False
    return False


def semantic_failure_reason(payload: Any, *, _path: str = "result", _depth: int = 0) -> str | None:
    if _depth > 8:
        return None
    if isinstance(payload, str):
        text = payload.strip()
        if not text or text[0] not in "{[":
            return None
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return None
    if not isinstance(payload, dict):
        return None
    if payload.get("success") is False:
        return _non_empty_error(payload.get("error")) or f"{_path}.success=false"
    error = _non_empty_error(payload.get("error"))
    if error:
        return error
    status = payload.get("status")
    if isinstance(status, str) and status.lower() in {"failed", "error"}:
        return (
            _non_empty_error(payload.get("error"))
            or _non_empty_error(payload.get("error_message"))
            or _non_empty_error(payload.get("reason"))
            or _non_empty_error(payload.get("message"))
            or f"{_path}.status={status}"
        )
    if "code" in payload and _legacy_code_failure(payload.get("code")):
        return (
            _non_empty_error(payload.get("message"))
            or _non_empty_error(payload.get("msg"))
            or _non_empty_error(payload.get("error"))
            or f"{_path}.code={payload.get('code')}"
        )
    for key in ("data", "result"):
        inner = payload.get(key)
        if isinstance(inner, (dict, str)):
            reason = semantic_failure_reason(inner, _path=f"{_path}.{key}", _depth=_depth + 1)
            if reason:
                return reason
    return None
