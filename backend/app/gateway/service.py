"""Gateway service layer — stable public API for model gateway operations.

Consumers should import from here instead of touching gateway router
implementation details or its internal config globals directly.
"""

from __future__ import annotations

import logging
from typing import AsyncGenerator

from .base import BaseProvider
from .config import DEFAULT_MODEL, MODEL_PROFILES, _config, resolve_api_key
from .local import LocalProvider
from .opencode_provider import OpenCodeProvider
from .openai_provider import OpenAIProvider
from .router import ModelGatewayRouter, RetryBudget

logger = logging.getLogger("v2.gateway.service")

_GATEWAY_ROUTER = ModelGatewayRouter()


def list_model_profiles() -> list[dict]:
    return [
        {"key": key, "name": key, "provider": profile["provider"], "model": profile["model"]}
        for key, profile in MODEL_PROFILES.items()
    ]


def get_model_profile(profile_key: str) -> dict:
    profile = MODEL_PROFILES.get(profile_key) or MODEL_PROFILES.get(DEFAULT_MODEL)
    if not profile:
        raise RuntimeError("No LLM model profiles configured in models.json")
    return profile


def get_model_profile_safe(profile_key: str) -> dict | None:
    return MODEL_PROFILES.get(profile_key)


def get_model_provider(provider_name: str) -> BaseProvider:
    providers_config = _config.get("providers", {})
    cfg = providers_config.get(provider_name)
    if not cfg:
        if providers_config.get("local"):
            return LocalProvider()
        raise RuntimeError(f"Model provider '{provider_name}' is not configured")
    ptype = cfg.get("type", "")
    if ptype == "opencode":
        return OpenCodeProvider(api_url=cfg.get("api_url", ""))
    if ptype == "openai_compat":
        from app.config import get_settings
        api_key = resolve_api_key(cfg)
        return OpenAIProvider(
            api_url=cfg.get("api_url", ""),
            api_key=api_key,
            provider_name=cfg.get("provider_name", provider_name),
        )
    if ptype == "local":
        return LocalProvider()
    if providers_config.get("local"):
        return LocalProvider()
    raise RuntimeError(f"Model provider '{provider_name}' is not configured")


def get_fallback_chain() -> list[str]:
    return _config.get("model_types", {}).get("llm", {}).get("fallback_chain", [])


def get_default_model() -> str:
    return DEFAULT_MODEL


async def chat(
    messages: list[dict],
    profile_key: str = DEFAULT_MODEL,
    tools: list[dict] | None = None,
    budget: RetryBudget | None = None,
) -> dict:
    return await _GATEWAY_ROUTER.chat(messages=messages, profile_key=profile_key, tools=tools, budget=budget)


async def chat_stream(
    messages: list[dict],
    profile_key: str = DEFAULT_MODEL,
    tools: list[dict] | None = None,
) -> AsyncGenerator[dict, None]:
    async for event in _GATEWAY_ROUTER.chat_stream(messages=messages, profile_key=profile_key, tools=tools):
        yield event
