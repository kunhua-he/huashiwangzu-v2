"""FastAPI router for text-parser module.

Registers the parse capability with the framework's cross-module registry.
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.database import AsyncSessionLocal
from app.middleware.auth import require_permission
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.document_ir import DocumentIR, BlockIR, ManifestIR
from app.services.module_registry import register_capability
from app.services.file_reader import resolve_caller_user_id, read_uploaded_file

router = APIRouter(prefix="/api/text-parser", tags=["text-parser"])


class ParseRequest(BaseModel):
    file_id: int


async def _parse(params: dict, caller: str) -> dict:
    """Parse TXT/MD file into unified DocumentIR."""
    file_id = int(params.get("file_id", 0))
    if file_id <= 0:
        raise ValueError("file_id must be a positive integer")

    from pathlib import Path

    allowed = {"txt", "md", "markdown", "text", "log"}
    user_id = resolve_caller_user_id(caller)
    async with AsyncSessionLocal() as db:
        file, full_path = await read_uploaded_file(db, file_id, user_id, allowed)
        ext = (file.extension or "").lower()

        ALLOWED_ENCS = ["utf-8", "utf-8-sig", "gbk", "gb2312", "latin-1"]
        raw = full_path.read_bytes()
        content = None
        for enc in ALLOWED_ENCS:
            try:
                content = raw.decode(enc)
                break
            except (UnicodeDecodeError, LookupError):
                continue
        if content is None:
            content = raw.decode("utf-8", errors="replace")

        content = content.replace("\r\n", "\n").replace("\r", "\n")
        lines = content.splitlines(keepends=False)
        blocks = []
        is_md = ext in ("md", "markdown")

        if is_md:
            para_lines = []
            in_code_block = False
            for line in lines:
                if line.startswith("```"):
                    if para_lines:
                        text = "\n".join(para_lines).strip()
                        if text:
                            blocks.append({"type": "paragraph", "text": text, "page": None, "resource_ref": None})
                        para_lines = []
                    in_code_block = not in_code_block
                    blocks.append({"type": "code", "text": line, "page": None, "resource_ref": None})
                    continue
                if in_code_block:
                    blocks.append({"type": "code", "text": line, "page": None, "resource_ref": None})
                    continue
                if line.startswith("#"):
                    if para_lines:
                        text = "\n".join(para_lines).strip()
                        if text:
                            blocks.append({"type": "paragraph", "text": text, "page": None, "resource_ref": None})
                        para_lines = []
                    title_text = line.lstrip("#").strip()
                    blocks.append({"type": "heading", "text": title_text, "page": None, "resource_ref": None})
                    continue
                if line.strip() == "":
                    if para_lines:
                        text = "\n".join(para_lines).strip()
                        if text:
                            blocks.append({"type": "paragraph", "text": text, "page": None, "resource_ref": None})
                        para_lines = []
                    continue
                para_lines.append(line)
            if para_lines:
                text = "\n".join(para_lines).strip()
                if text:
                    blocks.append({"type": "paragraph", "text": text, "page": None, "resource_ref": None})
        else:
            para_lines = []
            for line in lines:
                if line.strip() == "":
                    if para_lines:
                        text = "\n".join(para_lines).strip()
                        if text:
                            blocks.append({"type": "paragraph", "text": text, "page": None, "resource_ref": None})
                        para_lines = []
                    continue
                para_lines.append(line)
            if para_lines:
                text = "\n".join(para_lines).strip()
                if text:
                    blocks.append({"type": "paragraph", "text": text, "page": None, "resource_ref": None})

    ir = DocumentIR(
        file_id=file_id,
        format=ext,
        manifest=ManifestIR(file_type=ext),
        blocks=blocks,
        resources=[],
    )
    return ir.model_dump(exclude_none=True)


@router.get("/health")
async def health():
    return ApiResponse(data={"module": "text-parser", "status": "ok"})


@router.post("/parse")
async def call_parse(payload: ParseRequest, user: User = Depends(require_permission("viewer"))):
    result = await _parse({"file_id": payload.file_id}, f"user:{user.id}")
    return ApiResponse(data=result)


register_capability(
    "text-parser", "parse", _parse,
    description="Parse TXT/MD files into unified content blocks",
    brief="解析文本文件",
    parameters={"file_id": {"type": "int"}},
    min_role="viewer",
)
