from app.middleware.auth import require_permission
from app.models.user import User
from app.schemas.common import ApiResponse
from app.services.module_registry import register_capability
from app.services.uploaded_file_runner import run_uploaded_file_capability
from fastapi import APIRouter, Depends
from pydantic import BaseModel

router = APIRouter(prefix="/api/pdf-parser", tags=["pdf-parser"])


class ParseRequest(BaseModel):
    file_id: int


async def _parse(params: dict, caller: str) -> dict:
    """Parse PDF file into unified content blocks. Called via cross-module capability."""
    import pdfplumber

    allowed = {"pdf"}

    def parse_file(file_id, _file, full_path, _ext):
        blocks = []
        resources = []
        resource_counter = 0

        with pdfplumber.open(str(full_path)) as pdf:
            for page_idx, page in enumerate(pdf.pages):
                pno = page_idx + 1

                text = page.extract_text() or ""
                lines = [line.rstrip() for line in text.splitlines() if line.strip()]
                if lines:
                    block_text = "\n".join(lines).strip()
                    if block_text:
                        block_type = "标题" if pno == 1 and len(lines) <= 5 else "段落"
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
                        blocks.append({"type": "表格", "text": table_text, "page": pno, "resource_ref": None})

                for img in page.images:
                    resource_counter += 1
                    xref = img.get("xref") or img.get("name", "")
                    blocks.append({"type": "图片", "text": "", "page": pno, "resource_ref": resource_counter})
                    resources.append({
                        "id": resource_counter,
                        "type": "图片",
                        "file_storage_id": None,
                        "text_desc": f"PDF page {pno} embedded image (xref={xref})",
                    })

        return {
            "file_id": file_id,
            "format": "pdf",
            "blocks": blocks,
            "resources": resources,
        }

    return await run_uploaded_file_capability(params, caller, allowed, parse_file)


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
