"""Agent 侧模型兼容层。只调用框架网关对象，不修改框架 adapter。"""
import json

from app.gateway.router import gateway_router


def _extract_raw_tool_calls(raw: dict) -> list[dict]:
    choices = raw.get("choices") or []
    if not choices:
        return []
    message = choices[0].get("message") or {}
    result = []
    for item in message.get("tool_calls") or []:
        fn = item.get("function") or {}
        args = fn.get("arguments") or {}
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                args = {}
        result.append({
            "id": item.get("id", ""),
            "type": item.get("type", "function"),
            "function": {
                "name": fn.get("name", ""),
                "arguments": args,
            },
        })
    return result


async def recover_tool_calls(messages: list[dict], profile_key: str, tools: list[dict]) -> dict:
    """当框架 adapter 漏抽 tool_calls 时，从 raw OpenAI-compatible 响应恢复。"""
    profile = gateway_router.get_profile(profile_key)
    provider = gateway_router.get_provider(profile["provider"])
    raw = await provider.chat(
        messages=messages,
        model=profile["model"],
        temperature=profile["temperature"],
        max_tokens=profile["max_tokens"],
        tools=tools,
    )
    choices = raw.get("choices") or []
    message = (choices[0].get("message") if choices else {}) or {}
    finish_reason = choices[0].get("finish_reason", "stop") if choices else "stop"
    return {
        "content": message.get("content", ""),
        "thinking": message.get("reasoning_content", ""),
        "tool_calls": _extract_raw_tool_calls(raw),
        "finish_reason": finish_reason,
    }
