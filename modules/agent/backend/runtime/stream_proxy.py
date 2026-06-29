from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from .stream_emitter import StreamEmitter


@dataclass
class StreamSegment:
    id: str
    kind: str
    started: bool = False
    closed: bool = False


class StreamProxy:
    """Manage assistant stream segment lifecycle for SSE output."""

    def __init__(self, emitter: StreamEmitter) -> None:
        self._emitter = emitter
        self._segments: dict[str, StreamSegment] = {}

    def new_segment(self, kind: str = "assistant") -> StreamSegment:
        segment = StreamSegment(id=f"{kind}_{uuid4().hex}", kind=kind)
        self._segments[segment.id] = segment
        return segment

    def start(self, segment: StreamSegment) -> bytes | None:
        if segment.started or segment.closed:
            return None
        segment.started = True
        return self._emitter.assistant_stream_start(segment.id)

    def delta(self, segment: StreamSegment, text: str) -> bytes | None:
        if not text or segment.closed:
            return None
        return self._emitter.assistant_stream_delta(segment.id, text)

    def rollback(self, segment: StreamSegment, reason: str, replacement: str = "") -> bytes | None:
        if segment.closed:
            return None
        segment.closed = True
        return self._emitter.assistant_stream_rollback(segment.id, reason, replacement=replacement)

    def commit(self, segment: StreamSegment) -> bytes | None:
        if segment.closed:
            return None
        segment.closed = True
        return self._emitter.assistant_stream_commit(segment.id)
