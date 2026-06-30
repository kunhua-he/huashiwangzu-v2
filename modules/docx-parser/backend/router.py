from app.middleware.auth import require_permission
from app.models.user import User
from app.schemas.common import ApiResponse
from app.services.module_registry import register_capability
from app.services.uploaded_file_runner import run_uploaded_file_capability
from fastapi import APIRouter, Depends
from pydantic import BaseModel

router = APIRouter(prefix="/api/docx-parser", tags=["docx-parser"])


class ParseRequest(BaseModel):
    file_id: int


async def _parse(params: dict, caller: str) -> dict:
    from docx import Document as DocxDocument
    import base64

    allowed = {"docx"}

    def parse_file(file_id, _file, full_path, _ext):
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
            blocks.append({"type": block_type, "text": text, "page": None, "resource_ref": None})

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
                img_bytes = b""
                try:
                    img_bytes = rel.target_part.blob
                except Exception:
                    pass
                blocks.append({"type": "image", "text": "", "page": None, "resource_ref": resource_counter})
                resources.append({
                    "id": resource_counter,
                    "type": "image",
                    "mime_type": rel.target_part.content_type if hasattr(rel, "target_part") and hasattr(rel.target_part, "content_type") else "image/png",
                    "filename": rel.target_ref.split("/")[-1] if "/" in (rel.target_ref or "") else "image.png",
                    "description": f"DOCX embedded image ({rel.target_ref})",
                    "_bytes_b64": base64.b64encode(img_bytes).decode("ascii") if img_bytes else "",
                })

        return {
            "file_id": file_id,
            "format": "docx",
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
