"""FastAPI router for image-gen module.

Placeholder implementation: generates a PIL-made placeholder image with
prompt text + watermark.  The real model adapter (_call_image_model) is
separated for easy swap-in later.
"""
import io
import logging
import re
import time

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.middleware.auth import require_permission
from app.models.user import User
from app.schemas.common import ApiResponse
from app.services.module_registry import register_capability

logger = logging.getLogger("v2.image-gen")

router = APIRouter(prefix="/api/image-gen", tags=["image-gen"])


# ---------------------------------------------------------------------------
# Real model adapter — THE ONLY function to change when hooking up real models
# ---------------------------------------------------------------------------

async def _call_image_model(
    prompt: str,
    size: str = "1024x1024",
    style: str = "",
    count: int = 1,
) -> list[bytes]:
    """Call the real image-generation model and return a list of PNG bytes.

    HOW TO INTEGRATE A REAL MODEL
    ------------------------------
    1. Set your API key in ``.env`` (e.g. ``IMAGE_GEN_API_KEY=sk-...``).
       NEVER hardcode a key here.
    2. Read the key via ``from app.config import get_settings;
       settings.IMAGE_GEN_API_KEY`` (add the field to your settings class first).
    3. Call your provider's API:
       - 即梦 (Jimeng)   – https://jimeng.jd.com
       - 通义万相 (Tongyi) – https://tongyi.aliyun.com
       - 豆包 (Doubao)   – https://www.doubao.com
       - Local SD        – http://127.0.0.1:7860/sdapi/v1/txt2img
    4. Return the raw image bytes (one per count).
    5. Update this docstring to document the chosen provider + env key name.

    Current placeholder behaviour
    -----------------------------
    Raises ``NotImplementedError`` so callers know no real model is wired yet.
    The capability handler catches it and produces a PIL placeholder instead.
    """
    raise NotImplementedError("Real image model not yet configured")


# ---------------------------------------------------------------------------
# Caller helper
# ---------------------------------------------------------------------------

def _resolve_user_id(caller: str) -> int:
    from app.core.exceptions import PermissionDenied
    try:
        prefix, raw_id = caller.split(":", 1)
        if prefix == "user":
            return int(raw_id)
    except (TypeError, ValueError):
        pass
    raise PermissionDenied("Invalid caller")


# ---------------------------------------------------------------------------
# PIL placeholder image generation
# ---------------------------------------------------------------------------

def _make_placeholder(prompt: str, width: int, height: int) -> bytes:
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (width, height), (245, 245, 245))
    draw = ImageDraw.Draw(img)

    watermark_text = "图片生成功能开发中"
    prompt_display = prompt if len(prompt) <= 60 else prompt[:57] + "..."

    font_large = None
    font_small = None
    for font_path in (
        "/System/Library/Fonts/PingFang.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
    ):
        try:
            font_large = ImageFont.truetype(font_path, 32)
            font_small = ImageFont.truetype(font_path, 24)
            break
        except (OSError, IOError):
            continue
    if font_large is None:
        font_large = ImageFont.load_default()
        font_small = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), prompt_display, font=font_large)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    tx = (width - tw) // 2
    ty = (height - th) // 2 - 30
    draw.text((tx, ty), prompt_display, fill=(60, 60, 60), font=font_large)

    wbbox = draw.textbbox((0, 0), watermark_text, font=font_small)
    ww = wbbox[2] - wbbox[0]
    wh = wbbox[3] - wbbox[1]
    wx = (width - ww) // 2
    wy = ty + th + 40
    draw.text((wx, wy), watermark_text, fill=(160, 160, 160), font=font_small)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Capability handler
# ---------------------------------------------------------------------------

async def _generate(params: dict, caller: str) -> dict:
    prompt = str(params.get("prompt", ""))
    size = str(params.get("size", "1024x1024"))
    style = str(params.get("style", ""))
    count = int(params.get("count", 1))

    if not prompt.strip():
        from app.core.exceptions import ValidationError
        raise ValidationError("prompt is required")

    match = re.match(r"^(\d+)\s*[xX]\s*(\d+)$", size.strip())
    if not match:
        from app.core.exceptions import ValidationError
        raise ValidationError("Invalid size format; expected e.g. 1024x1024")
    width, height = int(match.group(1)), int(match.group(2))

    user_id = _resolve_user_id(caller)

    try:
        image_bytes_list = await _call_image_model(prompt, size, style, count)
    except NotImplementedError:
        image_bytes_list = [_make_placeholder(prompt, width, height)]
        logger.info("Using placeholder image for prompt=%r", prompt[:80])

    from app.services.file_upload_service import upload_file

    ts = int(time.time() * 1000)
    results = []
    async with AsyncSessionLocal() as db:
        for idx, img_bytes in enumerate(image_bytes_list):
            filename = f"image-gen_{ts}_{idx+1}.png"
            file_obj = io.BytesIO(img_bytes)
            upload_result = await upload_file(
                db, file_obj, filename, user_id, folder_id=None,
            )
            results.append({
                "file_id": upload_result["id"],
                "name": upload_result["name"],
                "size": upload_result["size"],
                "placeholder": True,
                "explanation": "占位图，真实生成待接入",
            })

    return {
        "images": results,
        "placeholder": True,
        "explanation": "占位图，真实生成待接入",
    }


# ---------------------------------------------------------------------------
# HTTP endpoints
# ---------------------------------------------------------------------------

class GenerateRequest(BaseModel):
    prompt: str
    size: str = "1024x1024"
    style: str = ""
    count: int = 1


@router.get("/health")
async def health():
    return ApiResponse(data={"module": "image-gen", "status": "ok"})


@router.post("/generate")
async def call_generate(
    payload: GenerateRequest,
    user: User = Depends(require_permission("editor")),
):
    result = await _generate(payload.model_dump(), f"user:{user.id}")
    return ApiResponse(data=result)


# ---------------------------------------------------------------------------
# Register capability (Agent discovers this automatically)
# ---------------------------------------------------------------------------

register_capability(
    "image-gen", "generate", _generate,
    description="生成图片：根据提示词生成图片（当前为占位，真实生成待接入）",
    parameters={
        "prompt": {"type": "string", "description": "提示词，描述想要生成的图片内容"},
        "size": {"type": "string", "description": "尺寸，格式如 1024x1024", "default": "1024x1024"},
        "style": {"type": "string", "description": "风格提示词（可选）", "default": ""},
        "count": {"type": "integer", "description": "生成数量", "default": 1},
    },
    min_role="editor",
)
