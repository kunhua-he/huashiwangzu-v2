"""Raw vision collection stage."""
from __future__ import annotations

from .common import run_raw_collection_stage


async def run(**context: object) -> dict:
    return await run_raw_collection_stage(stage="raw_vision", **context)
