"""ant 协议(Anthropic /v1/messages)Provider。

独立成类(不塞进 OpenAIProvider,避免污染正在跑的 chat/res 路径)。
响应归一复用 adapters.AnthropicAdapter。按 2026-07-16 探针实测 1:1 对照:
- 端点 /v1/messages,认证 x-api-key(不是 Bearer)+ anthropic-version 头
- 请求体 messages[] + max_tokens必填 + system 顶层(不在 messages 里)
- 流式 SSE:event:/data: 格式,message_stop 结束(不是 [DONE])
- 部分服务商(jayce中转站)必须走代理,provider_cfg 传 proxy

网关只收/返,协议差异这一层吃掉,对上永远统一 ModelResponse/StreamEvent。
"""
from __future__ import annotations

import json
import logging
from typing import AsyncGenerator

import httpx

from .adapters.anthropic import AnthropicAdapter
from .base import BaseProvider
from .contract import stream_event_to_dict
from .protocol import normalize_openai_payload
from .stream_parse import error_message, extract_stream_payload

logger = logging.getLogger("v2.gateway.anthropic")

ANTHROPIC_VERSION = "2023-06-01"


class AnthropicProvider(BaseProvider):
    def __init__(
        self,
        api_url: str,
        api_key: str = "",
        provider_name: str = "anthropic",
        extra_headers: dict[str, str] | None = None,
        proxy: str = "",
        timeout_seconds: float = 120.0,
    ):
        self.api_url = api_url
        self.api_key = api_key
        self.provider_name = provider_name
        self.extra_headers = extra_headers or {}
        self.proxy = proxy or ""
        self.timeout_seconds = timeout_seconds
        # adapter 按协议定,不能按模型名(deepseek-v4-flash 会误命中 DeepSeekAdapter,
        # 那是 OpenAI choices 格式,吃不了 ant 的 content_block_delta)
        self._adapter = AnthropicAdapter()

    def _headers(self) -> dict[str, str]:
        headers = {
            "content-type": "application/json",
            "anthropic-version": ANTHROPIC_VERSION,
        }
        if self.api_key:
            headers["x-api-key"] = self.api_key
        headers.update({str(k): str(v) for k, v in self.extra_headers.items() if k and v})
        return headers

    def _client(self) -> httpx.AsyncClient:
        # 部分中转站必须走代理(trust_env=False 屏蔽环境代理,只认显式 proxy)
        if self.proxy:
            return httpx.AsyncClient(timeout=self.timeout_seconds, trust_env=False, proxy=self.proxy)
        return httpx.AsyncClient(timeout=self.timeout_seconds, trust_env=False)

    def _build_payload(
        self, messages: list[dict], model: str, temperature: float,
        max_tokens: int, stream: bool, tools: list[dict] | None,
    ) -> dict:
        normalized_messages, normalized_tools = normalize_openai_payload(messages, tools)
        system, convo = _split_system_and_messages(normalized_messages)
        data: dict = {
            "model": model,
            "messages": convo,
            "max_tokens": max_tokens,  # ant 必填
            "temperature": temperature,
            "stream": stream,
        }
        if system:
            data["system"] = system
        if normalized_tools:
            data["tools"] = _tools_to_anthropic(normalized_tools)
        return data

    async def chat(
        self, messages: list[dict], model: str, temperature: float = 0.7,
        max_tokens: int = 4096, tools: list[dict] | None = None,
        response_format: dict | None = None,
    ) -> dict:
        payload = self._build_payload(messages, model, temperature, max_tokens, False, tools)
        async with self._client() as client:
            resp = await client.post(self.api_url, json=payload, headers=self._headers())
            if resp.status_code >= 400:
                body = await _read_error_body(resp)
                logger.error("Anthropic provider %s 返回 %s\n响应体: %s",
                             self.provider_name, resp.status_code, body)
                return {"error": error_message(resp.status_code, body.encode())}
            return resp.json()

    async def chat_stream(
        self, messages: list[dict], model: str, temperature: float = 0.7,
        max_tokens: int = 4096, tools: list[dict] | None = None,
        response_format: dict | None = None,
    ) -> AsyncGenerator[dict, None]:
        adapter = self._adapter
        payload = self._build_payload(messages, model, temperature, max_tokens, True, tools)
        try:
            async with self._client() as client:
                async with client.stream("POST", self.api_url, json=payload, headers=self._headers()) as resp:
                    if resp.status_code >= 400:
                        yield {"type": "error", "content": error_message(resp.status_code, await resp.aread())}
                        return
                    async for line in resp.aiter_lines():
                        chunk = extract_stream_payload(line)
                        if chunk is None:
                            continue
                        try:
                            data = json.loads(chunk)
                        except json.JSONDecodeError:
                            continue
                        if data.get("type") == "error":
                            err = data.get("error") or {}
                            yield {"type": "error", "content": str(err.get("message") or err)}
                            return
                        event = adapter.adapt_stream_chunk(data, provider=self.provider_name)
                        if event:
                            yield stream_event_to_dict(event)
        except Exception as e:  # noqa: BLE001
            logger.error("Anthropic stream error: %s", e)
            yield {"type": "error", "content": str(e)}

    async def check_health(self) -> bool:
        try:
            async with self._client() as client:
                resp = await client.post(
                    self.api_url,
                    json={"model": "claude-3-5-haiku-20241022", "max_tokens": 1,
                          "messages": [{"role": "user", "content": "hi"}]},
                    headers=self._headers(),
                )
                # 4xx(认证/模型名)也算连通,只有连不上才不健康
                return resp.status_code < 500
        except Exception as e:  # noqa: BLE001
            logger.warning("Anthropic health check failed: %s", e)
            return False


def _split_system_and_messages(messages: list[dict]) -> tuple[str, list[dict]]:
    """ant 把 system 提到顶层,messages 里只留 user/assistant。"""
    system_parts: list[str] = []
    convo: list[dict] = []
    for m in messages:
        role = m.get("role")
        if role == "system":
            c = m.get("content")
            if isinstance(c, str) and c:
                system_parts.append(c)
            elif isinstance(c, list):
                for part in c:
                    if isinstance(part, dict) and part.get("text"):
                        system_parts.append(str(part["text"]))
            continue
        convo.append(m)
    return "\n\n".join(system_parts), convo


def _tools_to_anthropic(tools: list[dict]) -> list[dict]:
    """OpenAI function tools → Anthropic tools。"""
    out: list[dict] = []
    for t in tools:
        fn = t.get("function") if isinstance(t, dict) else None
        if not isinstance(fn, dict):
            continue
        out.append({
            "name": fn.get("name", ""),
            "description": fn.get("description", ""),
            "input_schema": fn.get("parameters") or {"type": "object", "properties": {}},
        })
    return out


async def _read_error_body(resp: httpx.Response) -> str:
    try:
        body = resp.text
        return body[:500] if len(body) > 500 else body
    except Exception:  # noqa: BLE001
        return "(无法读取响应体)"
