"""FastAPI router for docx-parser module.

Registers the parse capability with the framework's cross-module registry.
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.database import AsyncSessionLocal
from app.middleware.auth import require_permission
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.document_ir import DocumentIR, ManifestIR
from app.services.module_registry import register_capability
from app.services.file_reader import resolve_caller_user_id, read_uploaded_file

router = APIRouter(prefix="/api/docx-parser", tags=["docx-parser"])


class ParseRequest(BaseModel):
    file_id: int


async def _parse(params: dict, caller: str) -> dict:
    """Parse DOCX file into unified DocumentIR."""
    file_id = int(params.get("file_id", 0))
    if file_id <= 0:
        raise ValueError("file_id must be a positive integer")

    from docx import Document as DocxDocument

    allowed = {"docx"}
    user_id = resolve_caller_user_id(caller)
    async with AsyncSessionLocal() as db:
        _, full_path = await read_uploaded_file(db, file_id, user_id, allowed)

        doc = DocxDocument(str(full_path))
        blocks = []
        resources = []
        resource_counter = 0

        for para in doc.paragraphs:
            text = "\n".join(line.rstrip() for line in para.text.splitlines()).strip()
            if not text:
                continue
            style_name = str(para.style.name) if para.style else ""
            block_type = "heading" if ("heading" in style_name.lower() or "标题" in style_name) else "paragraph"
            level = None
            if block_type == "heading":
                for i in range(1, 10):
                    if str(i) in style_name or f"heading {i}" in style_name.lower():
                        level = i
                        break
            blocks.append({"type": block_type, "text": text, "level": level, "page": None, "resource_ref": None})

        for table in doc.tables:
            rows = []
            for row in table.rows:
                cells = [cell.text.strip() for cell in row.cells]
                rows.append(" | ".join(cells))
            table_text = "\n".join(rows)
            if table_text.strip():
                blocks.append({"type": "table", "text": table_text, "page": None, "resource_ref": None})

        for rel in doc.part.rels.values():
            if "image" in str(rel.reltype or "").lower():
                resource_counter += 1
                blocks.append({"type": "image", "text": "", "page": None, "resource_ref": resource_counter})
                resources.append({
                    "id": resource_counter,
                    "type": "image",
                    "file_storage_id": None,
                    "text_desc": f"DOCX embedded image ({rel.target_ref})",
                })

    ir = DocumentIR(
        file_id=file_id,
        format="docx",
        manifest=ManifestIR(file_type="docx"),
        blocks=blocks,
        resources=resources,
    )
    return ir.model_dump(exclude_none=True)


@router.get("/health")
async def health():
    return ApiResponse(data={"module": "docx-parser", "status": "ok"})


@router.post("/parse")
async def call_parse(payload: ParseRequest, user: User = Depends(require_permission("viewer"))):
    result = await _parse({"file_id": payload.file_id}, f"user:{user.id}")
    return ApiResponse(data=result)


register_capability(
    "docx-parser", "parse", _parse,
    description="Parse DOCX files into unified content blocks",
    brief="解析 DOCX 文档",
    parameters={"file_id": {"type": "int"}},
    min_role="viewer",
)
