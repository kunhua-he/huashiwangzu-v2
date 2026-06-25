"""Unified Document IR / Resource IR / Patch IR / Projection IR contracts.

These Pydantic models define the platform-level "document intermediate representation"
that all parsers, docs-open, office, office-gen, and agents share.

Design principles:
- Raw payload may still coexist, but normalized IR is the public fact source
- English block types throughout (no Chinese in the IR schema)
- Resources are first-class objects with provenance
- Patch IR carries the operation + lineage
- Projection IR describes write-back constraints
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


# ── Block types ──────────────────────────────────────────────────────

class BlockType(str, Enum):
    paragraph = "paragraph"
    heading = "heading"
    table = "table"
    image = "image"
    code = "code"
    list_item = "list_item"
    page_break = "page_break"


# ── Block IR ─────────────────────────────────────────────────────────

class BlockIR(BaseModel):
    """A single content block in the unified document IR."""
    type: BlockType
    text: str = ""
    level: int | None = None
    page: int | None = None
    resource_ref: int | str | None = None
    metadata: dict = Field(default_factory=dict)

    model_config = {"extra": "allow"}


# ── Resource IR ──────────────────────────────────────────────────────

class ResourceType(str, Enum):
    image = "image"
    table = "table"
    attachment = "attachment"
    embedded = "embedded"


class ResourceIR(BaseModel):
    """An embedded resource (image, attachment, table data) referenced by blocks."""
    id: int | str
    type: ResourceType
    storage_path: str | None = None
    mime_type: str | None = None
    text_desc: str | None = None
    metadata: dict = Field(default_factory=dict)

    model_config = {"extra": "allow"}


# ── Manifest IR ──────────────────────────────────────────────────────

class ManifestIR(BaseModel):
    """Document-level metadata manifest."""
    file_name: str = ""
    file_type: str = ""
    ir_version: str = "1.0"
    created_at: str | None = None
    updated_at: str | None = None
    total_blocks: int = 0
    total_resources: int = 0
    metadata: dict = Field(default_factory=dict)


# ── Document IR (the unified output) ────────────────────────────────

class DocumentIR(BaseModel):
    """Platform-level unified document intermediate representation.

    This is THE contract that all format-specific parsers converge to,
    and that all writers project from. Raw payload may coexist under
    ``raw``, but ``blocks`` + ``resources`` + ``manifest`` are the
    public fact source.
    """
    file_id: int
    format: str
    manifest: ManifestIR = Field(default_factory=ManifestIR)
    blocks: list[BlockIR] = Field(default_factory=list)
    resources: list[ResourceIR] = Field(default_factory=list)
    raw: dict | None = None

    model_config = {"extra": "allow"}


# ── Patch IR ─────────────────────────────────────────────────────────

class PatchOperation(str, Enum):
    replace_text = "replace_text"
    insert_block = "insert_block"
    delete_block = "delete_block"
    modify_block = "modify_block"
    replace_resource = "replace_resource"
    modify_cell = "modify_cell"
    insert_image = "insert_image"


class PatchTarget(BaseModel):
    """Where the patch applies in the IR tree."""
    block_index: int | None = None
    block_type: str | None = None
    json_path: str | None = None
    cell_ref: str | None = None


class PatchIR(BaseModel):
    """A patch operation against a DocumentIR."""
    operation: PatchOperation
    target: PatchTarget
    value: str | dict | list | None = None
    reason: str | None = None
    risk_level: str = "medium"


# ── Projection IR ────────────────────────────────────────────────────

class ProjectionTarget(str, Enum):
    docx = "docx"
    xlsx = "xlsx"
    pptx = "pptx"
    pdf = "pdf"
    txt = "txt"
    csv = "csv"
    md = "md"


class ProjectionIR(BaseModel):
    """Projection hints for writing DocumentIR back to a specific format.

    Each format projects the normalized IR through this description,
    allowing writers to know which blocks go where without re-parsing.
    """
    target: ProjectionTarget
    blocks: list[BlockIR] = Field(default_factory=list)
    resources: list[ResourceIR] = Field(default_factory=list)
    config: dict = Field(default_factory=dict)
