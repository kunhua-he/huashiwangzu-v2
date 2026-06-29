from __future__ import annotations

from abc import ABC, abstractmethod

from app.gateway.contract import ModelResponse, StreamEvent, StreamEventType, ToolCall, Usage


class ModelAdapter(ABC):
    @abstractmethod
    def adapt_response(self, raw: dict, provider: str = "") -> ModelResponse:
        ...

    @abstractmethod
    def adapt_stream_chunk(self, chunk: dict, provider: str = "") -> StreamEvent | None:
        ...


def _extract_ollama_content(raw: dict) -> str:
    return (raw.get("message") or {}).get("content", "")


def _extract_ollama_tool_calls(raw: dict) -> list[ToolCall]:
    msg = raw.get("message") or {}
    raw_calls = msg.get("tool_calls") or []
    result = []
    for tc in raw_calls:
        fn = tc.get("function", {})
        args_str = fn.get("arguments", {})
        if isinstance(args_str, str):
            import json
            try:
                args_str = json.loads(args_str)
            except json.JSONDecodeError:
                args_str = {}
        result.append(ToolCall(
            id=tc.get("id", ""),
            type="function",
            function={"name": fn.get("name", ""), "arguments": args_str},
        ))
    return result


def _extract_openai_tool_calls(choice: dict) -> list[ToolCall]:
    msg = choice.get("message") or {}
    raw_calls = msg.get("tool_calls") or []
    result = []
    for tc in raw_calls:
        fn = tc.get("function", {})
        args = fn.get("arguments", "{}")
        if isinstance(args, str):
            import json
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                args = {}
        result.append(ToolCall(
            id=tc.get("id", ""),
            type="function",
            function={"name": fn.get("name", ""), "arguments": args},
        ))
    return result


def _extract_openai_choice(raw: dict, idx: int = 0) -> dict:
    choices = raw.get("choices") or []
    if idx < len(choices):
        return choices[idx]
    return {}


def _extract_usage(raw: dict) -> Usage | None:
    u = raw.get("usage")
    if not u:
        return None
    pt = u.get("prompt_tokens") or u.get("input_tokens") or 0
    ct = u.get("completion_tokens") or u.get("output_tokens") or 0
    if pt <= 0 and ct <= 0:
        return None
    return Usage(prompt_tokens=pt, completion_tokens=ct, total_tokens=pt + ct)


def _build_unified(
    content: str = "",
    thinking: str = "",
    tool_calls: list[ToolCall] | None = None,
    finish_reason: str = "stop",
    usage: Usage | None = None,
) -> ModelResponse:
    return ModelResponse(
        content=content,
        thinking=thinking,
        tool_calls=tool_calls or [],
        finish_reason=finish_reason,
        usage=usage,
    )


def _build_stream_event(
    event_type: str,
    content: str = "",
    tool_calls: list[ToolCall] | None = None,
    usage: Usage | None = None,
) -> StreamEvent:
    return StreamEvent(type=event_type, content=content, tool_calls=tool_calls, usage=usage)


class OpenAICompatLikeAdapter(ModelAdapter):
    include_thinking: bool = False

    def adapt_response(self, raw: dict, provider: str = "") -> ModelResponse:
        return self._build_response(raw, provider)

    def adapt_stream_chunk(self, chunk: dict, provider: str = "") -> StreamEvent | None:
        return self._build_stream_chunk(chunk, provider)

    def _build_response(self, raw: dict, provider: str = "") -> ModelResponse:
        usage = _extract_usage(raw)
        if provider == "ollama":
            content = _extract_ollama_content(raw)
            tool_calls = _extract_ollama_tool_calls(raw)
            return _build_unified(content=content, tool_calls=tool_calls, usage=usage)
        choice = _extract_openai_choice(raw)
        msg = choice.get("message") or {}
        tool_calls = _extract_openai_tool_calls(choice)
        return _build_unified(
            content=msg.get("content", ""),
            thinking=msg.get("reasoning_content", "") if self.include_thinking else "",
            tool_calls=tool_calls,
            finish_reason=choice.get("finish_reason", "stop"),
            usage=usage,
        )

    def _build_stream_chunk(self, chunk: dict, provider: str = "") -> StreamEvent | None:
        if provider == "ollama":
            if chunk.get("done"):
                return _build_stream_event(StreamEventType.DONE)
            msg = chunk.get("message") or {}
            content = msg.get("content", "")
            tool_calls = msg.get("tool_calls")
            if tool_calls:
                return _build_stream_event(StreamEventType.TOOL_CALL, tool_calls=_extract_ollama_tool_calls(chunk))
            if content:
                return _build_stream_event(StreamEventType.TOKEN, content)
            return None
        choice = _extract_openai_choice(chunk)
        delta = choice.get("delta") or {}
        content = delta.get("content", "")
        thinking = delta.get("reasoning_content", "")
        tool_calls = delta.get("tool_calls")
        if tool_calls:
            return None
        if choice.get("finish_reason"):
            usage = _extract_usage(chunk)
            return _build_stream_event(StreamEventType.DONE, usage=usage)
        if self.include_thinking and thinking:
            return _build_stream_event(StreamEventType.THINKING, thinking)
        if content:
            return _build_stream_event(StreamEventType.TOKEN, content)
        return None


class OpenAICompatAdapter(OpenAICompatLikeAdapter):
    include_thinking = True


class GemmaAdapter(OpenAICompatLikeAdapter):
    include_thinking = False


class QwenAdapter(OpenAICompatLikeAdapter):
    include_thinking = False
