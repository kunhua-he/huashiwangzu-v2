import pytest
from app.gateway import router as gateway_router_module
from app.gateway.config import get_model_type_config
from app.gateway.contract import ModelRequest, ModelResponse
from app.gateway.local import LocalProvider
from app.gateway.router import ModelGatewayRouter, RetryBudget, _call_with_unified_retry
from app.services.model_watchdog import launcher as watchdog_launcher
from app.services.model_watchdog.registry import ModelRecord


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
    def __init__(self, message: str = "rate limit", status_code: int = 429) -> None:
        self.calls = 0
        self.message = message
        self.status_code = status_code

    async def chat(self, messages, model, temperature=0.7, max_tokens=4096, tools=None):
        self.calls += 1
        exc = RuntimeError(self.message)
        exc.status_code = self.status_code
        raise exc


class LocalSuccessProvider:
    def __init__(self, content: str = "local ok") -> None:
        self.calls = 0
        self.content = content

    async def chat(self, messages, model, temperature=0.7, max_tokens=4096, tools=None):
        self.calls += 1
        return {"content": self.content, "thinking": "", "finish_reason": "stop"}


class OpenAICompatSuccessProvider:
    def __init__(self, content: str = "ok", provider_shape: str = "openai") -> None:
        self.calls = 0
        self.content = content
        self.provider_shape = provider_shape

    async def chat(self, messages, model, temperature=0.7, max_tokens=4096, tools=None):
        self.calls += 1
        if self.provider_shape == "ollama":
            return {"message": {"role": "assistant", "content": self.content}, "done": True}
        return {"choices": [{"message": {"content": self.content}, "finish_reason": "stop"}]}


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
    assert result["diagnostics"]["fallback_used"] is True
    assert result["diagnostics"]["selected_profile"] == "local-fallback"


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
    assert result["diagnostics"]["attempts"][0]["profile"] == "cloud-primary"
    assert cloud.calls == 1
    assert local.calls == 0


@pytest.mark.asyncio
async def test_configured_llm_chain_prefers_llama_cpp_then_ollama() -> None:
    llm_cfg = get_model_type_config("llm")
    profiles = llm_cfg["profiles"]

    assert llm_cfg["primary"] == "deepseek-v4-flash"
    assert llm_cfg["fallback_chain"][:2] == ["gemma-4", "ollama-local"]
    assert profiles["gemma-4"]["provider"] == "llama"
    assert profiles["gemma-4"]["watchdog"] == "gemma-4"
    assert profiles["ollama-local"]["provider"] == "ollama"


@pytest.mark.asyncio
async def test_cloud_auth_failure_falls_back_to_llama_with_diagnostics(monkeypatch) -> None:
    profiles = {
        "cloud-primary": {
            "provider": "cloud",
            "model": "cloud-primary",
            "temperature": 0.7,
            "max_tokens": 128,
        },
        "gemma-4": {
            "provider": "llama",
            "model": "gemma-4",
            "temperature": 0.2,
            "max_tokens": 64,
            "watchdog": "gemma-4",
        },
    }
    cloud = AlwaysFailProvider("invalid api key", status_code=401)
    llama = OpenAICompatSuccessProvider("llama fallback ok")

    async def ensure_ok(profile):
        return None

    monkeypatch.setattr(gateway_router_module, "MODEL_PROFILES", profiles)
    monkeypatch.setattr(gateway_router_module, "_ensure_local_text_model", ensure_ok)
    monkeypatch.setattr(
        gateway_router_module,
        "get_model_type_config",
        lambda model_type: {
            "primary": "cloud-primary",
            "fallback_on_explicit_profile": True,
            "fallback_chain": ["gemma-4"],
            "profiles": profiles,
        } if model_type == "llm" else {},
    )

    router = ModelGatewayRouter.__new__(ModelGatewayRouter)
    router._providers = {"cloud": cloud, "llama": llama}

    result = await router.chat(
        messages=[{"role": "user", "content": "hello"}],
        profile_key="cloud-primary",
        budget=RetryBudget(max_attempts=1),
    )

    assert result["content"] == "llama fallback ok"
    assert result["diagnostics"]["fallback_used"] is True
    assert result["diagnostics"]["selected_profile"] == "gemma-4"
    assert result["diagnostics"]["attempts"][0]["provider"] == "cloud"
    assert result["diagnostics"]["attempts"][0]["success"] is False
    assert result["diagnostics"]["attempts"][1]["provider"] == "llama"
    assert result["diagnostics"]["attempts"][1]["success"] is True


@pytest.mark.asyncio
async def test_cloud_5xx_retries_then_falls_back_to_llama(monkeypatch) -> None:
    profiles = {
        "cloud-primary": {
            "provider": "cloud",
            "model": "cloud-primary",
            "temperature": 0.7,
            "max_tokens": 128,
        },
        "gemma-4": {
            "provider": "llama",
            "model": "gemma-4",
            "temperature": 0.2,
            "max_tokens": 64,
            "watchdog": "gemma-4",
        },
    }
    cloud = AlwaysFailProvider("bad gateway", status_code=502)
    llama = OpenAICompatSuccessProvider("llama after 5xx ok")

    async def ensure_ok(profile):
        return None

    monkeypatch.setattr(gateway_router_module, "MODEL_PROFILES", profiles)
    monkeypatch.setattr(gateway_router_module, "_ensure_local_text_model", ensure_ok)
    monkeypatch.setattr(
        gateway_router_module,
        "get_model_type_config",
        lambda model_type: {
            "primary": "cloud-primary",
            "fallback_on_explicit_profile": True,
            "fallback_chain": ["gemma-4"],
            "profiles": profiles,
        } if model_type == "llm" else {},
    )

    router = ModelGatewayRouter.__new__(ModelGatewayRouter)
    router._providers = {"cloud": cloud, "llama": llama}

    result = await router.chat(
        messages=[{"role": "user", "content": "hello"}],
        profile_key="cloud-primary",
        budget=RetryBudget(max_attempts=2, base_delay_seconds=0.0),
    )

    assert result["content"] == "llama after 5xx ok"
    assert cloud.calls == 2
    assert llama.calls == 1
    assert result["diagnostics"]["fallback_used"] is True
    assert result["diagnostics"]["attempts"][0]["provider"] == "cloud"
    assert result["diagnostics"]["attempts"][0]["success"] is False
    assert result["diagnostics"]["attempts"][1]["provider"] == "llama"
    assert result["diagnostics"]["attempts"][1]["success"] is True


@pytest.mark.asyncio
async def test_llama_startup_failure_falls_through_to_ollama(monkeypatch) -> None:
    profiles = {
        "cloud-primary": {
            "provider": "cloud",
            "model": "cloud-primary",
            "temperature": 0.7,
            "max_tokens": 128,
        },
        "gemma-4": {
            "provider": "llama",
            "model": "gemma-4",
            "temperature": 0.2,
            "max_tokens": 64,
            "watchdog": "gemma-4",
        },
        "ollama-local": {
            "provider": "ollama",
            "model": "qwen2.5:7b",
            "temperature": 0.2,
            "max_tokens": 64,
        },
    }
    cloud = AlwaysFailProvider("quota exhausted", status_code=402)
    llama = OpenAICompatSuccessProvider("should not be called")
    ollama = OpenAICompatSuccessProvider("ollama fallback ok", provider_shape="ollama")

    async def ensure_fails(profile):
        raise FileNotFoundError("llama.cpp server binary is not configured")

    monkeypatch.setattr(gateway_router_module, "MODEL_PROFILES", profiles)
    monkeypatch.setattr(gateway_router_module, "_ensure_local_text_model", ensure_fails)
    monkeypatch.setattr(
        gateway_router_module,
        "get_model_type_config",
        lambda model_type: {
            "primary": "cloud-primary",
            "fallback_on_explicit_profile": True,
            "fallback_chain": ["gemma-4", "ollama-local"],
            "profiles": profiles,
        } if model_type == "llm" else {},
    )

    router = ModelGatewayRouter.__new__(ModelGatewayRouter)
    router._providers = {"cloud": cloud, "llama": llama, "ollama": ollama}

    result = await router.chat(
        messages=[{"role": "user", "content": "hello"}],
        profile_key="cloud-primary",
        budget=RetryBudget(max_attempts=1),
    )

    assert result["content"] == "ollama fallback ok"
    assert llama.calls == 0
    assert ollama.calls == 1
    assert result["diagnostics"]["attempts"][1]["stage"] == "health"
    assert result["diagnostics"]["attempts"][1]["provider"] == "llama"
    assert result["diagnostics"]["selected_profile"] == "ollama-local"


@pytest.mark.asyncio
async def test_local_fallback_exhaustion_returns_stable_diagnostics(monkeypatch) -> None:
    profiles = {
        "cloud-primary": {
            "provider": "cloud",
            "model": "cloud-primary",
            "temperature": 0.7,
            "max_tokens": 128,
        },
        "gemma-4": {
            "provider": "llama",
            "model": "gemma-4",
            "temperature": 0.2,
            "max_tokens": 64,
            "watchdog": "gemma-4",
        },
        "ollama-local": {
            "provider": "ollama",
            "model": "qwen2.5:7b",
            "temperature": 0.2,
            "max_tokens": 64,
        },
    }
    cloud = AlwaysFailProvider("quota exhausted", status_code=402)
    ollama = AlwaysFailProvider("connection refused", status_code=503)

    async def ensure_fails(profile):
        raise FileNotFoundError("Configured model file missing for gemma-4")

    monkeypatch.setattr(gateway_router_module, "MODEL_PROFILES", profiles)
    monkeypatch.setattr(gateway_router_module, "_ensure_local_text_model", ensure_fails)
    monkeypatch.setattr(
        gateway_router_module,
        "get_model_type_config",
        lambda model_type: {
            "primary": "cloud-primary",
            "fallback_on_explicit_profile": True,
            "fallback_chain": ["gemma-4", "ollama-local"],
            "profiles": profiles,
        } if model_type == "llm" else {},
    )

    router = ModelGatewayRouter.__new__(ModelGatewayRouter)
    router._providers = {"cloud": cloud, "ollama": ollama}

    result = await router.chat(
        messages=[{"role": "user", "content": "hello"}],
        profile_key="cloud-primary",
        budget=RetryBudget(max_attempts=1),
    )

    assert result["error"] == "connection refused"
    assert result["content"].startswith("(Model fallback exhausted:")
    diagnostics = result["diagnostics"]
    assert diagnostics["fallback_used"] is False
    assert "selected_profile" not in diagnostics
    assert diagnostics["candidates"] == ["cloud-primary", "gemma-4", "ollama-local"]
    assert [attempt["profile"] for attempt in diagnostics["attempts"]] == [
        "cloud-primary",
        "gemma-4",
        "ollama-local",
    ]
    assert diagnostics["attempts"][1]["stage"] == "health"
    assert "Configured model file missing" in diagnostics["attempts"][1]["error"]
    assert diagnostics["attempts"][2]["provider"] == "ollama"


@pytest.mark.asyncio
async def test_local_echo_provider_is_disabled_by_default() -> None:
    provider = LocalProvider()

    result = await provider.chat(
        messages=[{"role": "user", "content": "hello"}],
        model="local-test",
    )

    assert "error" in result
    assert await provider.check_health() is False


def test_watchdog_llama_launch_command_uses_configured_model_root(monkeypatch, tmp_path) -> None:
    model_file = tmp_path / "文本模型" / "demo.gguf"
    model_file.parent.mkdir()
    model_file.write_text("fake gguf", encoding="utf-8")
    monkeypatch.setenv("LLAMA_CPP_SERVER_BIN", "/bin/echo")
    monkeypatch.setattr(
        watchdog_launcher,
        "get_models_config",
        lambda: {
            "local_bin": {
                "llama_server_env": "LLAMA_CPP_SERVER_BIN",
                "model_root_env": "LOCAL_MODEL_ROOT",
                "model_root": str(tmp_path),
            }
        },
    )
    record = ModelRecord(
        name="demo",
        purpose="text",
        endpoint="http://127.0.0.1:39999",
        health_path="/v1/models",
        model_type="local",
        port=39999,
        launch={
            "backend": "llama.cpp",
            "model_path": "文本模型/demo.gguf",
            "args": ["-m", "{model_path}", "--port", "{port}"],
        },
    )

    command = watchdog_launcher._build_launch_command(record)

    assert command == ["/bin/echo", "-m", str(model_file), "--port", "39999"]


def test_watchdog_llama_launch_command_fails_fast_for_missing_model(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("LLAMA_CPP_SERVER_BIN", "/bin/echo")
    monkeypatch.setattr(
        watchdog_launcher,
        "get_models_config",
        lambda: {
            "local_bin": {
                "llama_server_env": "LLAMA_CPP_SERVER_BIN",
                "model_root": str(tmp_path),
            }
        },
    )
    record = ModelRecord(
        name="missing-demo",
        purpose="text",
        endpoint="http://127.0.0.1:39999",
        health_path="/v1/models",
        model_type="local",
        port=39999,
        launch={
            "backend": "llama.cpp",
            "model_path": "文本模型/missing.gguf",
        },
    )

    with pytest.raises(FileNotFoundError, match="Configured model file missing"):
        watchdog_launcher._build_launch_command(record)


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
