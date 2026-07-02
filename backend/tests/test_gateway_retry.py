import pytest
from app.gateway import router as gateway_router_module
from app.gateway.contract import ModelRequest, ModelResponse
from app.gateway.router import ModelGatewayRouter, RetryBudget, _call_with_unified_retry


class RetryableProvider:
    def __init__(self) -> None:
        self.calls = 0

    async def chat(self, messages, model, temperature=0.7, max_tokens=4096, tools=None):
        self.calls += 1
        if self.calls < 2:
            exc = RuntimeError("temporary upstream failure")
            exc.status_code = 502
            raise exc
        return {"choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}]}


class NonRetryableProvider:
    async def chat(self, messages, model, temperature=0.7, max_tokens=4096, tools=None):
        exc = RuntimeError("invalid api key")
        exc.status_code = 401
        raise exc


class ProtocolErrorProvider:
    def __init__(self) -> None:
        self.calls = 0

    async def chat(self, messages, model, temperature=0.7, max_tokens=4096, tools=None):
        self.calls += 1
        exc = RuntimeError("invalid_request_error: tool_calls must be followed by tool messages")
        exc.status_code = 400
        raise exc


class AlwaysFailProvider:
    def __init__(self, message: str = "rate limit") -> None:
        self.calls = 0
        self.message = message

    async def chat(self, messages, model, temperature=0.7, max_tokens=4096, tools=None):
        self.calls += 1
        exc = RuntimeError(self.message)
        exc.status_code = 429
        raise exc


class LocalSuccessProvider:
    def __init__(self, content: str = "local ok") -> None:
        self.calls = 0
        self.content = content

    async def chat(self, messages, model, temperature=0.7, max_tokens=4096, tools=None):
        self.calls += 1
        return {"content": self.content, "thinking": "", "finish_reason": "stop"}


@pytest.mark.asyncio
async def test_retryable_provider_is_retried_once() -> None:
    provider = RetryableProvider()
    result = await _call_with_unified_retry(
        provider=provider,
        req=ModelRequest(messages=[], temperature=0.7, max_tokens=1),
        model="demo",
        caller_module="test",
        profile_key="demo",
        provider_name="test",
    )
    assert isinstance(result, ModelResponse)
    assert result.content == "ok"
    assert provider.calls == 2


@pytest.mark.asyncio
async def test_non_retryable_provider_returns_error_response() -> None:
    provider = NonRetryableProvider()
    result = await _call_with_unified_retry(
        provider=provider,
        req=ModelRequest(messages=[], temperature=0.7, max_tokens=1),
        model="demo",
        caller_module="test",
        profile_key="demo",
        provider_name="test",
    )
    assert isinstance(result, ModelResponse)
    assert result.error is not None
    assert "invalid api key" in result.error


@pytest.mark.asyncio
async def test_protocol_error_is_not_retried() -> None:
    provider = ProtocolErrorProvider()
    result = await _call_with_unified_retry(
        provider=provider,
        req=ModelRequest(messages=[], temperature=0.7, max_tokens=1),
        model="demo",
        caller_module="test",
        profile_key="demo",
        provider_name="test",
    )
    assert isinstance(result, ModelResponse)
    assert result.error is not None
    assert "tool_calls must be followed" in result.error
    assert provider.calls == 1


@pytest.mark.asyncio
async def test_chat_falls_back_from_explicit_cloud_profile(monkeypatch) -> None:
    profiles = {
        "cloud-primary": {
            "provider": "cloud",
            "model": "cloud-primary",
            "temperature": 0.7,
            "max_tokens": 128,
        },
        "local-fallback": {
            "provider": "local",
            "model": "local-fallback",
            "temperature": 0.2,
            "max_tokens": 64,
        },
    }
    cloud = AlwaysFailProvider("quota exhausted")
    local = LocalSuccessProvider("local fallback ok")

    monkeypatch.setattr(gateway_router_module, "MODEL_PROFILES", profiles)
    monkeypatch.setattr(
        gateway_router_module,
        "get_model_type_config",
        lambda model_type: {
            "primary": "cloud-primary",
            "fallback_on_explicit_profile": True,
            "fallback_chain": ["local-fallback"],
            "profiles": profiles,
        } if model_type == "llm" else {},
    )

    router = ModelGatewayRouter.__new__(ModelGatewayRouter)
    router._providers = {"cloud": cloud, "local": local}

    result = await router.chat(
        messages=[{"role": "user", "content": "hello"}],
        profile_key="cloud-primary",
        budget=RetryBudget(max_attempts=1),
    )

    assert result["content"] == "local fallback ok"
    assert "error" not in result
    assert cloud.calls == 1
    assert local.calls == 1


@pytest.mark.asyncio
async def test_chat_stops_fallback_on_protocol_error(monkeypatch) -> None:
    profiles = {
        "cloud-primary": {
            "provider": "cloud",
            "model": "cloud-primary",
            "temperature": 0.7,
            "max_tokens": 128,
        },
        "local-fallback": {
            "provider": "local",
            "model": "local-fallback",
            "temperature": 0.2,
            "max_tokens": 64,
        },
    }
    cloud = AlwaysFailProvider("tool_calls must be followed by tool messages")
    local = LocalSuccessProvider("should not run")

    monkeypatch.setattr(gateway_router_module, "MODEL_PROFILES", profiles)
    monkeypatch.setattr(
        gateway_router_module,
        "get_model_type_config",
        lambda model_type: {
            "primary": "cloud-primary",
            "fallback_on_explicit_profile": True,
            "fallback_chain": ["local-fallback"],
            "profiles": profiles,
        } if model_type == "llm" else {},
    )

    router = ModelGatewayRouter.__new__(ModelGatewayRouter)
    router._providers = {"cloud": cloud, "local": local}

    result = await router.chat(
        messages=[{"role": "user", "content": "hello"}],
        profile_key="cloud-primary",
        budget=RetryBudget(max_attempts=1),
    )

    assert "error" in result
    assert "tool_calls must be followed" in result["error"]
    assert cloud.calls == 1
    assert local.calls == 0


@pytest.mark.asyncio
async def test_describe_image_falls_back_from_explicit_vision_profile(monkeypatch) -> None:
    profiles = {
        "mimo": {
            "provider": "mimo",
            "model": "mimo-v2.5",
            "temperature": 0.7,
            "max_tokens": 128,
        },
        "qwen3-vl": {
            "provider": "local",
            "model": "qwen3-vl",
            "temperature": 0.2,
            "max_tokens": 64,
        },
    }
    mimo = AlwaysFailProvider("vision quota exhausted")
    local = LocalSuccessProvider("本地视觉描述")

    monkeypatch.setattr(gateway_router_module, "_VISION_PRIMARY", "mimo")
    monkeypatch.setattr(gateway_router_module, "_VISION_FALLBACK", ["qwen3-vl"])
    monkeypatch.setattr(gateway_router_module, "_VISION_PROFILES", profiles)
    monkeypatch.setattr(
        gateway_router_module,
        "get_model_type_config",
        lambda model_type: {
            "primary": "mimo",
            "fallback_on_explicit_profile": True,
            "fallback_chain": ["qwen3-vl"],
            "profiles": profiles,
        } if model_type == "vision" else {},
    )

    router = ModelGatewayRouter.__new__(ModelGatewayRouter)
    router._providers = {"mimo": mimo, "local": local}

    result = await router.describe_image(
        image_bytes=b"not-really-an-image",
        profile_key="mimo",
        mime_type="image/png",
    )

    assert result == "本地视觉描述"
    assert mimo.calls == 1
    assert local.calls == 1
