"""Unified Document Intermediate Representation (IR).

All parsers produce this structure. Knowledge ingestion, chunking, fusion,
and export consume only this IR, never raw parser output.

A DocumentIr is the single contract between format-specific parsers and
the knowledge pipeline. Adding a new format = writing one parser that
returns a DocumentIr; no downstream code changes needed.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

BlockType = Literal[
    "heading", "paragraph", "table", "list", "code", "image",
    "figure", "formula", "quote", "separator", "divider",
    "sheet", "range", "cell_patch", "slide", "chart",
]

BlockLevel = Literal["block", "inline"]


class Coordinate(BaseModel):
    x: float = 0.0
    y: float = 0.0
    w: float = 0.0
    h: float = 0.0


class ResourceRef(BaseModel):
    id: int
    type: str = ""
    mime_type: str = ""
    storage_path: str | None = None
    text_desc: str = ""


class ContentBlock(BaseModel):
    type: BlockType = "paragraph"
    text: str = ""
    page: int | None = None
    resource_ref: int | None = None
    hierarchy_level: int = 0
    coordinate: Coordinate | None = None
    children: list[ContentBlock] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentIr(BaseModel):
    file_id: int
    format: str = ""
    total_pages: int = 1
    blocks: list[ContentBlock] = Field(default_factory=list)
    resources: list[ResourceRef] = Field(default_factory=list)
    parsed_at: str = ""
    parse_errors: list[str] = Field(default_factory=list)
    parse_status: str = "ok"
    resource_diagnostics: list[dict] = Field(default_factory=list)
    source_filename: str = ""
    source_size: int = 0

    def iter_non_empty(self) -> list[ContentBlock]:
        return [b for b in self._iter_all() if b.text.strip()]

    def _iter_all(self) -> list[ContentBlock]:
        result: list[ContentBlock] = []
        stack = list(self.blocks)
        while stack:
            b = stack.pop(0)
            result.append(b)
            if b.children:
                stack = b.children + stack
        return result


CANONICAL_BLOCK_TYPES = {
    "heading", "paragraph", "table", "list", "code", "image", "figure", "formula", "quote", "separator",
    "divider", "sheet", "range", "cell_patch", "slide", "chart",
}


LEGACY_BLOCK_TYPES = {
    "标题": ("heading", 1),
    "段落": ("paragraph", 0),
    "表格": ("table", 0),
    "图片": ("image", 0),
    "代码": ("code", 0),
    "融合": ("paragraph", 0),
}


LEGACY_OUTPUT_TYPES = {
    "heading": "标题",
    "paragraph": "段落",
    "table": "表格",
    "image": "图片",
    "figure": "图片",
    "code": "代码",
    "sheet": "标题",
    "slide": "标题",
}


def _normalize_block_type(value: object) -> tuple[str, int]:
    raw = str(value or "")
    if raw in LEGACY_BLOCK_TYPES:
        return LEGACY_BLOCK_TYPES[raw]
    if raw in CANONICAL_BLOCK_TYPES:
        level = 1 if raw in {"heading", "sheet", "slide"} else 0
        return raw, level
    return "paragraph", 0


def _block_metadata(block: dict) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    data = block.get("data")
    if isinstance(data, dict):
        metadata.update(data)
    source_ref = block.get("source_ref")
    if isinstance(source_ref, dict):
        metadata.setdefault("source_ref", source_ref)
    return metadata


def _content_block_from_dict(block: dict) -> ContentBlock:
    block_type, level = _normalize_block_type(block.get("type", ""))
    children = [
        _content_block_from_dict(child)
        for child in block.get("children") or []
        if isinstance(child, dict)
    ]
    return ContentBlock(
        type=block_type,
        text=str(block.get("text") or ""),
        page=block.get("page"),
        resource_ref=block.get("resource_ref"),
        hierarchy_level=level,
        children=children,
        metadata=_block_metadata(block),
    )


def from_legacy_blocks(
    file_id: int, fmt: str, blocks: list[dict],
    resources: list[dict] | None = None,
    resource_diagnostics: list[dict] | None = None,
    parse_status: str = "ok",
) -> DocumentIr:
    ir_blocks = [_content_block_from_dict(b) for b in blocks if isinstance(b, dict)]
    ir_resources = []
    if resources:
        for r in resources:
            stored_id = r.get("stored_resource_id")
            ir_resources.append(ResourceRef(
                id=stored_id or r.get("id", 0),
                type=r.get("type", ""),
                mime_type=r.get("mime_type", ""),
                text_desc=r.get("text_desc", ""),
            ))
    diagnostics: list[dict] = []
    if resource_diagnostics:
        diagnostics = list(resource_diagnostics)
    return DocumentIr(
        file_id=file_id,
        format=fmt,
        blocks=ir_blocks,
        resources=ir_resources,
        parsed_at=datetime.now().isoformat(),
        resource_diagnostics=diagnostics,
        parse_status=parse_status,
    )


def to_legacy_dict(ir: DocumentIr) -> dict:
    block_dicts = []
    for b in ir._iter_all():
        block_dicts.append({
            "type": LEGACY_OUTPUT_TYPES.get(b.type, "段落"),
            "text": b.text,
            "page": b.page,
            "resource_ref": b.resource_ref,
        })
    resource_dicts = [
        {"id": r.id, "type": r.type, "file_storage_id": None, "text_desc": r.text_desc,
         "stored_resource_id": r.id, "mime_type": r.mime_type}
        for r in ir.resources
    ]
    return {
        "file_id": ir.file_id,
        "format": ir.format,
        "blocks": block_dicts,
        "resources": resource_dicts,
        "parse_status": ir.parse_status,
        "resource_diagnostics": list(ir.resource_diagnostics),
    }
