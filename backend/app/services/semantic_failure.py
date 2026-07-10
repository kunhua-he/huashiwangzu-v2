"""Shared semantic-failure contract for success-shaped payloads."""

from __future__ import annotations

import json


def _non_empty_error(value: object) -> str | None:
    if value in (None, ""):
        return None
    if isinstance(value, str):
        text = value.strip()
        return text or None
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    except TypeError:
        return str(value)


def _legacy_code_failure(value: object) -> bool:
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


def semantic_failure_reason(result: object, *, _path: str = "result", _depth: int = 0) -> str | None:
    """Return a reason when a result payload is semantically failed.

    This is the shared boundary rule for module calls, background tasks, event
    handlers, and pipeline wrappers. Non-empty ``error`` is failure even when a
    transport envelope says ``success=true``.
    """
    if _depth > 8:
        return None
    if isinstance(result, str):
        text = result.strip()
        if not text or text[0] not in "{[":
            return None
        try:
            result = json.loads(text)
        except json.JSONDecodeError:
            return None
    if not isinstance(result, dict):
        return None

    if result.get("success") is False:
        return _non_empty_error(result.get("error")) or f"{_path}.success=false"

    error = _non_empty_error(result.get("error"))
    if error:
        return error

    status = result.get("status")
    if isinstance(status, str) and status.lower() in {"failed", "error"}:
        return (
            _non_empty_error(result.get("error"))
            or _non_empty_error(result.get("error_message"))
            or _non_empty_error(result.get("reason"))
            or _non_empty_error(result.get("message"))
            or f"{_path}.status={status}"
        )

    if "code" in result and _legacy_code_failure(result.get("code")):
        return (
            _non_empty_error(result.get("message"))
            or _non_empty_error(result.get("msg"))
            or _non_empty_error(result.get("error"))
            or f"{_path}.code={result.get('code')}"
        )

    for key in ("data", "result"):
        inner = result.get(key)
        if isinstance(inner, (dict, str)):
            inner_reason = semantic_failure_reason(inner, _path=f"{_path}.{key}", _depth=_depth + 1)
            if inner_reason:
                return inner_reason
    return None
