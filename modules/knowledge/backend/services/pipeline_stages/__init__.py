"""Independent execution entry points for knowledge pipeline stages."""
from __future__ import annotations

from typing import Awaitable, Callable

from . import (
    cognitive_index,
    fusion,
    graph,
    page_render,
    parse_index,
    profile,
    raw_ocr,
    raw_text,
    raw_vision,
    relations,
    source_validate,
)

StageRunner = Callable[..., Awaitable[dict]]

STAGE_RUNNERS: dict[str, StageRunner] = {
    "source_validate": source_validate.run,
    "parse_index": parse_index.run,
    "raw_text": raw_text.run,
    "page_render": page_render.run,
    "raw_ocr": raw_ocr.run,
    "raw_vision": raw_vision.run,
    "fusion": fusion.run,
    "profile": profile.run,
    "cognitive_index": cognitive_index.run,
    "graph": graph.run,
    "relations": relations.run,
}


async def run_pipeline_stage(stage: str, **context: object) -> dict:
    """Dispatch one durable stage to its module-local node implementation."""
    runner = STAGE_RUNNERS.get(stage)
    if runner is None:
        document_id = getattr(context.get("doc"), "id", None)
        return {"document_id": document_id, "status": "failed", "error": f"unknown stage {stage}"}
    return await runner(**context)
