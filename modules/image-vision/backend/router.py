from app.middleware.auth import require_permission
from app.models.user import User
from app.schemas.common import ApiResponse
from app.services.module_registry import register_capability
from app.services.uploaded_file_runner import run_uploaded_file_capability
from fastapi import APIRouter, Depends
from pydantic import BaseModel

router = APIRouter(prefix="/api/image-vision", tags=["image-vision"])


class DescribeRequest(BaseModel):
    file_id: int


async def _describe(params: dict, caller: str) -> dict:
    import io

    allowed = {"jpg", "jpeg", "png", "gif", "webp", "bmp", "ico"}

    async def describe_file(file_id, file, full_path, ext):
        raw = full_path.read_bytes()
        fmt_map = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "gif": "gif",
                   "webp": "webp", "bmp": "bmp", "ico": "png"}
        mime_fmt = fmt_map.get(ext, "jpeg")

        # Try gateway vision model; fallback to metadata only
        try:
            from app.services.model_services import describe_image
            description = await describe_image(
                raw,
                prompt="请详细描述这张图片中的内容，包括文字、物体、布局等。",
                mime_type=f"image/{mime_fmt}",
            )
        except Exception as exc:
            try:
                from PIL import Image
                img = Image.open(io.BytesIO(raw))
                dims = f"{img.width}x{img.height}"
                description = f"[Image metadata] {file.name}.{file.extension}, {dims}px, mode={img.mode}. Vision unavailable: {exc}"
            except Exception:
                description = f"[Image metadata] {file.name}.{file.extension}, {len(raw)} bytes. Vision unavailable."

        blocks = [
            {"type": "image", "text": description, "page": None, "resource_ref": 1},
        ]
        resources = [
            {"id": 1, "type": "image", "file_storage_id": file_id, "text_desc": description},
        ]

        return {
            "file_id": file_id,
            "format": ext,
            "blocks": blocks,
            "resources": resources,
        }

    return await run_uploaded_file_capability(params, caller, allowed, describe_file)


@router.get("/health")
async def health():
    return ApiResponse(data={"module": "image-vision", "status": "ok"})


@router.post("/describe")
async def call_describe(payload: DescribeRequest, user: User = Depends(require_permission("viewer"))):
    result = await _describe({"file_id": payload.file_id}, f"user:{user.id}")
    return ApiResponse(data=result)


register_capability(
    "image-vision", "describe", _describe,
    description="Generate text description of images via vision model",
    brief="识别图片内容",
    parameters={"file_id": {"type": "int"}},
    min_role="viewer",
)
