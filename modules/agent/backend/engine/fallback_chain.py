"""Agent model gateway wrapper.

Fallback is owned by the framework gateway. This module keeps the historical
function names used by Agent while avoiding a second fallback loop.
"""
import logging
from typing import AsyncGenerator

from app.gateway.router import gateway_router

logger = logging.getLogger("v2.agent").getChild("engine.fallback_chain")


async def chat_with_fallback(
    messages: list[dict],
    profile_key: str,
    tools: list[dict] | None = None,
    conversation_id: int | None = None,
    response_format: dict | None = None,
) -> dict:
    _ = conversation_id
    kwargs = {
        "messages": messages,
        "profile_key": profile_key,
        "tools": tools,
    }
    if response_format is not None:
        kwargs["response_format"] = response_format
    return await gateway_router.chat(
        **kwargs,
    )


def _extract_reason(exc: Exception) -> str:
    detail = str(exc)
    if hasattr(exc, "response"):
        try:
            body = exc.response.text
            if body:
                detail = f"{detail[:200]} | 响应体:{body[:500]}"
        except Exception:
            pass
    return detail[:300]


async def chat_stream_with_fallback(
    messages: list[dict],
    profile_key: str,
    tools: list[dict] | None = None,
    conversation_id: int | None = None,
    response_format: dict | None = None,
) -> AsyncGenerator[dict, None]:
    _ = conversation_id
    kwargs = {
        "messages": messages,
        "profile_key": profile_key,
        "tools": tools,
    }
    if response_format is not None:
        kwargs["response_format"] = response_format
    async for event in gateway_router.chat_stream(
        **kwargs,
    ):
        yield event
