from app.middleware.auth import require_permission
from app.models.user import User
from app.schemas.common import ApiResponse
from app.services.module_registry import register_capability
from app.services.uploaded_file_runner import run_uploaded_file_capability
from fastapi import APIRouter, Depends
from pydantic import BaseModel

router = APIRouter(prefix="/api/pptx-parser", tags=["pptx-parser"])


class ParseRequest(BaseModel):
    file_id: int


async def _parse(params: dict, caller: str) -> dict:
    from pptx import Presentation

    allowed = {"pptx"}

    def parse_file(file_id, _file, full_path, _ext):
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

    return await run_uploaded_file_capability(params, caller, allowed, parse_file)


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
