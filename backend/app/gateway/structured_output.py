from __future__ import annotations


def response_format_for_chat_completions(response_format: dict | None) -> dict | None:
    if response_format is None:
        return None
    return dict(response_format)


def response_format_for_responses_api(response_format: dict | None) -> dict | None:
    if response_format is None:
        return None
    normalized = dict(response_format)
    if normalized.get("type") == "json_schema" and isinstance(normalized.get("json_schema"), dict):
        return {
            "type": "json_schema",
            **normalized["json_schema"],
        }
    return normalized
