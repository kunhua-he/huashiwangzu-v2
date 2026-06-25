"""FastAPI router for pptx-parser module.

Registers the parse capability with the framework's cross-module registry.
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.database import AsyncSessionLocal
from app.middleware.auth import require_permission
from app.models.user import User
from app.schemas.common import ApiResponse
from app.services.module_registry import register_capability
from app.services.file_reader import resolve_caller_user_id, read_uploaded_file

router = APIRouter(prefix="/api/pptx-parser", tags=["pptx-parser"])


class ParseRequest(BaseModel):
    file_id: int


async def _parse(params: dict, caller: str) -> dict:
    """Parse PPTX file into unified content blocks."""
    file_id = int(params.get("file_id", 0))
    if file_id <= 0:
        raise ValueError("file_id must be a positive integer")

    from pptx import Presentation

    allowed = {"pptx"}
    user_id = resolve_caller_user_id(caller)
    async with AsyncSessionLocal() as db:
        _, full_path = await read_uploaded_file(db, file_id, user_id, allowed)

        prs = Presentation(str(full_path))
        blocks = []
        resources = []
        resource_counter = 0

        for slide_idx, slide in enumerate(prs.slides):
            pno = slide_idx + 1
            for shape in slide.shapes:
                if shape.has_text_frame:
                    for para in shape.text_frame.paragraphs:
                        text = para.text.strip()
                        if not text:
                            continue
                        block_type = "标题" if ("title" in str(shape.name).lower() or "标题" in str(shape.name)) else "段落"
                        blocks.append({"type": block_type, "text": text, "page": pno, "resource_ref": None})
                if shape.shape_type and "picture" in str(shape.shape_type).lower():
                    resource_counter += 1
                    blocks.append({"type": "图片", "text": "", "page": pno, "resource_ref": resource_counter})
                    resources.append({
                        "id": resource_counter,
                        "type": "图片",
                        "file_storage_id": None,
                        "text_desc": f"Slide {pno} image ({shape.name})",
                    })

    return {
        "file_id": file_id,
        "format": "pptx",
        "blocks": blocks,
        "resources": resources,
    }


@router.get("/health")
async def health():
    return ApiResponse(data={"module": "pptx-parser", "status": "ok"})


@router.post("/parse")
async def call_parse(payload: ParseRequest, user: User = Depends(require_permission("viewer"))):
    result = await _parse({"file_id": payload.file_id}, f"user:{user.id}")
    return ApiResponse(data=result)


register_capability(
    "pptx-parser", "parse", _parse,
    description="Parse PPTX files into unified content blocks",
    brief="解析 PPTX 文档",
    parameters={"file_id": {"type": "int"}},
    min_role="viewer",
)
