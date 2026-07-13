from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
from app.gateway import router as router_module
from app.gateway.openai_provider import OpenAIProvider
from app.gateway.router import ModelGatewayRouter

RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "demo_result",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {"ok": {"type": "boolean"}},
            "required": ["ok"],
            "additionalProperties": False,
        },
    },
}


class CapturingProvider:
    def __init__(self) -> None:
        self.chat_response_format: dict | None = None
        self.stream_response_format: dict | None = None

    async def chat(
        self,
        messages: list[dict],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        tools: list[dict] | None = None,
        response_format: dict | None = None,
    ) -> dict:
        self.chat_response_format = response_format
        return {
            "choices": [{
                "message": {"content": '{"ok":true}'},
                "finish_reason": "stop",
            }],
        }

    async def chat_stream(
        self,
        messages: list[dict],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        tools: list[dict] | None = None,
        response_format: dict | None = None,
    ) -> AsyncGenerator[dict, None]:
        self.stream_response_format = response_format
        yield {"type": "token", "content": '{"ok":true}'}
        yield {"type": "done", "content": ""}


def test_openai_payload_carries_chat_completions_response_format() -> None:
    provider = OpenAIProvider(api_url="https://example.test/v1/chat/completions")

    payload = provider._build_payload(
        [], "demo", 0.1, 100, False, None, RESPONSE_FORMAT,
    )

    assert payload["response_format"] == RESPONSE_FORMAT


def test_openai_payload_converts_response_format_for_responses_api() -> None:
    provider = OpenAIProvider(
        api_url="https://example.test/v1/responses",
        api_protocol="responses",
    )

    payload = provider._build_payload(
        [], "demo", 0.1, 100, False, None, RESPONSE_FORMAT,
    )

    assert payload["text"]["format"] == {
        "type": "json_schema",
        **RESPONSE_FORMAT["json_schema"],
    }
    assert "response_format" not in payload


@pytest.mark.asyncio
async def test_gateway_router_passes_response_format_to_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile = {
        "provider": "capture",
        "model": "demo-model",
        "temperature": 0.1,
        "max_tokens": 100,
    }
    monkeypatch.setattr(router_module, "MODEL_PROFILES", {"demo": profile})
    provider = CapturingProvider()
    router = ModelGatewayRouter()
    router._providers = {"capture": provider}

    result = await router.chat(
        messages=[{"role": "user", "content": "return json"}],
        profile_key="demo",
        response_format=RESPONSE_FORMAT,
    )
    events = [
        event
        async for event in router.chat_stream(
            messages=[{"role": "user", "content": "return json"}],
            profile_key="demo",
            response_format=RESPONSE_FORMAT,
        )
    ]

    assert result["content"] == '{"ok":true}'
    assert provider.chat_response_format == RESPONSE_FORMAT
    assert provider.stream_response_format == RESPONSE_FORMAT
    assert events[-1]["type"] == "done"
