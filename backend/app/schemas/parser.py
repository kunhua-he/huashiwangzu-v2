"""Unified ParseResult contract for all 5 parser modules."""

from pydantic import BaseModel


class ParseResult(BaseModel):
    file_id: int
    format: str
    blocks: list[dict]
    resources: list[dict]
