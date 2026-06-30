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
    import base64

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

                    img_bytes = b""
                    try:
                        import fitz
                        pdf_doc = fitz.open(str(full_path))
                        try:
                            pix = pdf_doc[page_idx].get_pixmap()
                            img_bytes = pix.tobytes("png")
                        finally:
                            pdf_doc.close()
                    except ImportError:
                        pass

                    resources.append({
                        "id": resource_counter,
                        "type": "image",
                        "mime_type": "image/png",
                        "filename": f"page{pno}_xref{xref}.png",
                        "description": f"PDF page {pno} embedded image (xref={xref})",
                        "_bytes_b64": base64.b64encode(img_bytes).decode("ascii") if img_bytes else "",
                    })

        return {
            "file_id": file_id,
            "format": "pdf",
            "blocks": blocks,
            "resources": resources,
        }

    result = await run_uploaded_file_capability(params, caller, allowed, parse_file)

    from app.services.module_registry import call_capability
    for res in result.get("resources", []):
        data_b64 = res.pop("_bytes_b64", "")
        if data_b64:
            try:
                await call_capability(
                    "content", "store_resource",
                    {
                        "data_b64": data_b64,
                        "resource_type": "image",
                        "mime_type": res.get("mime_type", "image/png"),
                        "filename": res.get("filename", "resource.png"),
                        "description": res.get("description", ""),
                    },
                    caller,
                )
            except Exception:
                pass

    return result


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
