from __future__ import annotations

from dataclasses import dataclass, field

from .contract import ToolCall


@dataclass
class _PartialToolCall:
    id: str = ""
    type: str = "function"
    name_parts: list[str] = field(default_factory=list)
    argument_parts: list[str] = field(default_factory=list)

    def to_tool_call(self) -> ToolCall:
        return ToolCall(
            id=self.id,
            type=self.type or "function",
            function={
                "name": "".join(self.name_parts),
                "arguments": "".join(self.argument_parts),
            },
        )


class StreamingToolCallAccumulator:
    """Accumulate OpenAI-compatible streaming tool-call deltas.

    Providers may split ``function.arguments`` across arbitrary chunks.  The
    chunks are not valid JSON until the provider finishes with
    ``finish_reason='tool_calls'``, so this accumulator preserves raw argument
    text and only exposes completed calls when asked by the stream owner.
    """

    def __init__(self) -> None:
        self._items: dict[int, _PartialToolCall] = {}

    def add_delta_tool_calls(self, raw_calls: list[dict] | None) -> None:
        if not raw_calls:
            return
        for fallback_index, raw_call in enumerate(raw_calls):
            if not isinstance(raw_call, dict):
                continue
            index = raw_call.get("index")
            if not isinstance(index, int):
                index = fallback_index
            item = self._items.setdefault(index, _PartialToolCall())

            call_id = raw_call.get("id")
            if isinstance(call_id, str) and call_id:
                item.id = call_id
            call_type = raw_call.get("type")
            if isinstance(call_type, str) and call_type:
                item.type = call_type

            function = raw_call.get("function") or {}
            if not isinstance(function, dict):
                continue
            name = function.get("name")
            if isinstance(name, str) and name:
                item.name_parts.append(name)
            arguments = function.get("arguments")
            if isinstance(arguments, str) and arguments:
                item.argument_parts.append(arguments)

    def has_calls(self) -> bool:
        return bool(self._items)

    def completed_tool_calls(self) -> list[ToolCall]:
        return [self._items[index].to_tool_call() for index in sorted(self._items)]
