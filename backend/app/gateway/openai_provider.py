from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import uuid
from typing import AsyncGenerator

import httpx

from app.config import get_settings

from .adapters import get_adapter
from .base import BaseProvider
from .contract import StreamEvent, StreamEventType, stream_event_to_dict
from .protocol import normalize_openai_payload
from .stream_parse import error_message, extract_stream_payload, format_error
from .tool_call_accumulator import StreamingToolCallAccumulator

logger = logging.getLogger("v2.gateway.openai_compat")

OPENCODE_API_URL = "https://opencode.ai/zen/go/v1/chat/completions"


class OpenAIProvider(BaseProvider):
    def __init__(
        self,
        api_url: str,
        api_key: str = "",
        provider_name: str = "opencode",
        extra_headers: dict[str, str] | None = None,
        session_affinity: dict | None = None,
        auth_recovery: dict | None = None,
        api_protocol: str = "",
    ):
        self.api_url = api_url
        self.api_key = api_key
        self.provider_name = provider_name
        self.extra_headers = extra_headers or {}
        self.session_affinity = session_affinity or {}
        self.auth_recovery = auth_recovery or {}
        self.api_protocol = (api_protocol or self._infer_api_protocol(api_url)).strip().lower()

    @staticmethod
    def _infer_api_protocol(api_url: str) -> str:
        return "responses" if str(api_url or "").rstrip("/").endswith("/responses") else "chat_completions"

    def _headers(self, payload: dict | None = None, model: str = "") -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        headers.update({str(k): str(v) for k, v in self.extra_headers.items() if k and v})
        session_header = str(self.session_affinity.get("header") or "").strip()
        if session_header and payload is not None:
            prefix = str(self.session_affinity.get("prefix") or self.provider_name or "gateway").strip()
            scope = str(self.session_affinity.get("scope") or "payload").strip().lower()
            if scope == "request":
                headers[session_header] = _request_session_id(prefix=prefix)
            else:
                headers[session_header] = _payload_session_id(prefix=prefix, model=model, payload=payload)
        return headers

    def _build_payload(
        self, messages: list[dict], model: str, temperature: float,
        max_tokens: int, stream: bool, tools: list[dict] | None,
        response_format: dict | None = None,
    ) -> dict:
        normalized_messages, normalized_tools = normalize_openai_payload(messages, tools)
        if self.api_protocol == "responses":
            data = {
                "model": model,
                "input": _responses_input_from_messages(normalized_messages),
                "temperature": temperature,
                "max_output_tokens": max_tokens,
                "stream": stream,
                "store": False,
            }
            instructions = _responses_instructions_from_messages(normalized_messages)
            if instructions:
                data["instructions"] = instructions
            if normalized_tools:
                data["tools"] = normalized_tools
            if response_format:
                responses_format = dict(response_format)
                if (
                    responses_format.get("type") == "json_schema"
                    and isinstance(responses_format.get("json_schema"), dict)
                ):
                    responses_format = {
                        "type": "json_schema",
                        **responses_format["json_schema"],
                    }
                data["text"] = {"format": responses_format}
            return data
        data = {
            "model": model,
            "messages": normalized_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
        }
        if normalized_tools:
            data["tools"] = normalized_tools
        if response_format:
            data["response_format"] = response_format
        return data

    async def chat(
        self, messages: list[dict], model: str, temperature: float = 0.7,
        max_tokens: int = 4096, tools: list[dict] | None = None,
        response_format: dict | None = None,
    ) -> dict:
        payload = self._build_payload(
            messages, model, temperature, max_tokens, False, tools, response_format,
        )
        recovery = _auth_recovery_settings(self.auth_recovery)
        timeout = float(self.auth_recovery.get("timeout_seconds") or 120)
        async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
            for attempt in range(1, recovery["max_attempts"] + 1):
                try:
                    resp = await client.post(self.api_url, json=payload, headers=self._headers(payload, model))
                except Exception as exc:
                    should_recover = (
                        recovery["strategy"] == "rotate_session"
                        and _is_recoverable_exception(exc, recovery["exception_names"])
                        and attempt < recovery["max_attempts"]
                        and bool(str(self.session_affinity.get("header") or "").strip())
                    )
                    if should_recover:
                        logger.warning(
                            "AI provider %s raised %s; rotating session header %s (%d/%d)",
                            self.provider_name,
                            type(exc).__name__,
                            self.session_affinity.get("header"),
                            attempt,
                            recovery["max_attempts"],
                        )
                        delay = recovery["delay_seconds"]
                        if delay > 0:
                            await asyncio.sleep(delay)
                        continue
                    raise
                if resp.status_code < 400:
                    return resp.json()

                body_text = await _read_error_body(resp)
                payload_preview = _payload_preview(payload)
                should_recover = (
                    recovery["strategy"] == "rotate_session"
                    and resp.status_code in recovery["status_codes"]
                    and attempt < recovery["max_attempts"]
                    and bool(str(self.session_affinity.get("header") or "").strip())
                )
                if should_recover:
                    logger.warning(
                        "AI provider %s returned %s; rotating session header %s (%d/%d)",
                        self.provider_name,
                        resp.status_code,
                        self.session_affinity.get("header"),
                        attempt,
                        recovery["max_attempts"],
                    )
                    delay = recovery["delay_seconds"]
                    if delay > 0:
                        await asyncio.sleep(delay)
                    continue

                logger.error(
                    "AI provider %s returned %s\n请求体: %s\n响应体: %s",
                    self.provider_name, resp.status_code, payload_preview, body_text,
                )
                resp.raise_for_status()
        raise RuntimeError("OpenAI-compatible provider recovery exhausted without response")

    async def chat_stream(
        self, messages: list[dict], model: str, temperature: float = 0.7,
        max_tokens: int = 4096, tools: list[dict] | None = None,
        response_format: dict | None = None,
    ) -> AsyncGenerator[dict, None]:
        adapter = get_adapter(model)
        accumulator = StreamingToolCallAccumulator()
        payload = self._build_payload(
            messages, model, temperature, max_tokens, True, tools, response_format,
        )
        try:
            async with httpx.AsyncClient(timeout=300, trust_env=False) as client:
                async with client.stream("POST", self.api_url, json=payload, headers=self._headers(payload, model)) as resp:
                    if resp.status_code >= 400:
                        yield {"type": "error", "content": error_message(resp.status_code, await resp.aread())}
                        return
                    async for line in resp.aiter_lines():
                        chunk = extract_stream_payload(line)
                        if chunk is None:
                            continue
                        if chunk == "[DONE]":
                            yield {"type": "done", "content": ""}
                            return
                        try:
                            data = json.loads(chunk)
                        except json.JSONDecodeError:
                            continue
                        if "error" in data:
                            yield {"type": "error", "content": format_error(data["error"])}
                            return
                        choices = data.get("choices") or []
                        choice = choices[0] if choices else {}
                        delta = choice.get("delta") or {}
                        accumulator.add_delta_tool_calls(delta.get("tool_calls"))

                        # 在 finish_reason / [DONE] 之前提取 usage，确保即使 tool_call
                        # 导致下游提前 return，token 计数也不会丢失
                        _usage_raw = data.get("usage")
                        if _usage_raw:
                            yield {"type": "usage", "usage": _usage_raw}

                        if choice.get("finish_reason") == "tool_calls" and accumulator.has_calls():
                            yield stream_event_to_dict(
                                StreamEvent(
                                    type=StreamEventType.TOOL_CALL,
                                    tool_calls=accumulator.completed_tool_calls(),
                                )
                            )
                            continue
                        event = adapter.adapt_stream_chunk(data, provider=self.provider_name)
                        if event:
                            yield stream_event_to_dict(event)
                            if event.type == StreamEventType.DONE:
                                return
        except Exception as e:
            logger.error("OpenAI-compatible stream error: %s", e)
            yield {"type": "error", "content": str(e)}

    async def check_health(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5, trust_env=False) as client:
                resp = await client.get(_models_url_for_api_url(self.api_url), headers=self._headers())
                return resp.status_code == 200
        except Exception as e:
            logger.warning("OpenAI-compatible health check failed: %s", e)
            return False


async def _read_error_body(resp: httpx.Response) -> str:
    try:
        body = resp.text
        return body[:500] if len(body) > 500 else body
    except Exception:
        return "(无法读取响应体)"


def _auth_recovery_settings(config: dict) -> dict:
    strategy = str(config.get("strategy") or "").strip().lower()
    raw_status_codes = config.get("status_codes") or []
    status_codes = {
        int(code)
        for code in raw_status_codes
        if str(code).strip().isdigit()
    }
    max_attempts = int(config.get("max_attempts") or 1)
    delay_seconds = float(config.get("delay_seconds") or 0)
    raw_exception_names = config.get("exception_names") or config.get("exceptions") or []
    exception_names = {
        str(name).strip()
        for name in raw_exception_names
        if str(name).strip()
    }
    if strategy != "rotate_session" or (not status_codes and not exception_names):
        max_attempts = 1
    return {
        "strategy": strategy,
        "status_codes": status_codes,
        "exception_names": exception_names,
        "max_attempts": max(1, max_attempts),
        "delay_seconds": max(0.0, delay_seconds),
    }


def _is_recoverable_exception(exc: Exception, names: set[str]) -> bool:
    exc_type = type(exc)
    candidates = {
        exc_type.__name__,
        f"{exc_type.__module__}.{exc_type.__name__}",
    }
    return bool(candidates & names)


class OpenCodeProvider(OpenAIProvider):
    def __init__(self, api_url: str = "", api_key: str = ""):
        super().__init__(
            api_url=api_url or OPENCODE_API_URL,
            api_key=api_key or get_settings().DEEPSEEK_API_KEY,
            provider_name="opencode",
        )


def _models_url_for_api_url(api_url: str) -> str:
    url = str(api_url or "").rstrip("/")
    for suffix in ("/chat/completions", "/responses"):
        if url.endswith(suffix):
            return f"{url[:-len(suffix)]}/models"
    return f"{url}/models"


def _responses_instructions_from_messages(messages: list[dict]) -> str:
    parts: list[str] = []
    for message in messages:
        if str(message.get("role") or "") != "system":
            continue
        content = message.get("content")
        if isinstance(content, str):
            parts.append(content)
        elif isinstance(content, list):
            parts.extend(
                str(item.get("text"))
                for item in content
                if isinstance(item, dict) and item.get("type") in {"text", "input_text"} and item.get("text")
            )
    return "\n\n".join(part for part in parts if part)


def _responses_input_from_messages(messages: list[dict]) -> list[dict]:
    result: list[dict] = []
    for message in messages:
        role = str(message.get("role") or "user")
        if role == "system":
            continue
        result.append({
            "role": role,
            "content": _responses_content_parts(message.get("content")),
        })
    return result


def _responses_content_parts(content: object) -> list[dict]:
    if isinstance(content, str):
        return [{"type": "input_text", "text": content}]
    if not isinstance(content, list):
        return [{"type": "input_text", "text": str(content or "")}]

    parts: list[dict] = []
    for item in content:
        if isinstance(item, str):
            parts.append({"type": "input_text", "text": item})
            continue
        if not isinstance(item, dict):
            continue
        item_type = item.get("type")
        if item_type in {"text", "input_text"}:
            parts.append({"type": "input_text", "text": str(item.get("text") or "")})
            continue
        if item_type == "image_url" or "image_url" in item:
            image_url = item.get("image_url")
            url = image_url.get("url") if isinstance(image_url, dict) else image_url
            if url:
                parts.append({"type": "input_image", "image_url": str(url)})
    return parts or [{"type": "input_text", "text": ""}]


def _payload_session_id(prefix: str, model: str, payload: dict) -> str:
    raw = json.dumps(
        {"model": model, "payload": payload},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    digest = hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()[:32]
    clean_prefix = "".join(ch if ch.isalnum() or ch in {"-", "_", ":"} else "-" for ch in prefix)[:48]
    return f"{clean_prefix}:{digest}" if clean_prefix else digest


def _request_session_id(prefix: str) -> str:
    clean_prefix = "".join(ch if ch.isalnum() or ch in {"-", "_", ":"} else "-" for ch in prefix)[:48]
    digest = uuid.uuid4().hex
    return f"{clean_prefix}:{digest}" if clean_prefix else digest


def _payload_preview(payload: dict) -> str:
    return json.dumps(_redact_payload_for_log(payload), ensure_ascii=False, default=str)[:2000]


def _redact_payload_for_log(value):
    if isinstance(value, dict):
        redacted = {}
        for key, item in value.items():
            if key == "url" and isinstance(item, str) and item.startswith("data:image/"):
                redacted[key] = "<image data url redacted>"
            else:
                redacted[key] = _redact_payload_for_log(item)
        return redacted
    if isinstance(value, list):
        return [_redact_payload_for_log(item) for item in value]
    if isinstance(value, str) and value.startswith("data:image/"):
        return "<image data url redacted>"
    return value
