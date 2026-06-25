"""FastAPI router for pdf-parser module.

Registers the parse capability with the framework's cross-module registry.
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.database import AsyncSessionLocal
from app.middleware.auth import require_permission
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.document_ir import DocumentIR, ManifestIR, ResourceIR
from app.services.module_registry import register_capability
from app.services.file_reader import resolve_caller_user_id, read_uploaded_file

router = APIRouter(prefix="/api/pdf-parser", tags=["pdf-parser"])


class ParseRequest(BaseModel):
    file_id: int


async def _parse(params: dict, caller: str) -> dict:
    """Parse PDF file into unified content blocks. Called via cross-module capability."""
    file_id = int(params.get("file_id", 0))
    if file_id <= 0:
        raise ValueError("file_id must be a positive integer")

    import pdfplumber

    allowed = {"pdf"}
    user_id = resolve_caller_user_id(caller)
    async with AsyncSessionLocal() as db:
        _, full_path = await read_uploaded_file(db, file_id, user_id, allowed)

        blocks = []
        resources = []
        resource_counter = 0

        with pdfplumber.open(str(full_path)) as pdf:
            for page_idx, page in enumerate(pdf.pages):
                pno = page_idx + 1

                text = page.extract_text() or ""
                lines = [l.rstrip() for l in text.splitlines() if l.strip()]
                if lines:
                    block_text = "\n".join(lines).strip()
                    if block_text:
                        block_type = "heading" if pno == 1 and len(lines) <= 5 else "paragraph"
                        blocks.append({"type": block_type, "text": block_text, "page": pno, "resource_ref": None})

                tables = page.extract_tables()
                for table in tables:
                    if not table:
                        continue
                    rows = []
                    for row in table:
                        cells = [str(c).strip() if c else "" for c in row]
                        rows.append(" | ".join(cells))
                    table_text = "\n".join(rows)
                    if table_text.strip():
                        blocks.append({"type": "table", "text": table_text, "page": pno, "resource_ref": None})

                for img in page.images:
                    resource_counter += 1
                    xref = img.get("xref") or img.get("name", "")
                    blocks.append({"type": "image", "text": "", "page": pno, "resource_ref": resource_counter})
                    resources.append({
                        "id": resource_counter,
                        "type": "image",
                        "file_storage_id": None,
                        "text_desc": f"PDF page {pno} embedded image (xref={xref})",
                    })

    ir = DocumentIR(
        file_id=file_id,
        format="pdf",
        manifest=ManifestIR(file_type="pdf"),
        blocks=blocks,
        resources=resources,
    )
    return ir.model_dump(exclude_none=True)


@router.get("/health")
async def health():
    return ApiResponse(data={"module": "pdf-parser", "status": "ok"})


@router.post("/parse")
async def call_parse(payload: ParseRequest, user: User = Depends(require_permission("viewer"))):
    result = await _parse({"file_id": payload.file_id}, f"user:{user.id}")
    return ApiResponse(data=result)


# Register capability at import time
register_capability(
    "pdf-parser", "parse", _parse,
    description="Parse PDF files into unified content blocks",
    brief="解析 PDF 文档",
    parameters={"file_id": {"type": "int", "description": "File ID in file storage"}},
    min_role="viewer",
)
