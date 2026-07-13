from __future__ import annotations

import hashlib
import io
import logging
import os
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.exceptions import NotFound, PermissionDenied, ValidationError
from app.gateway.vision_preprocess import allow_large_image_decode
from app.models.file import File, FileDerivative
from app.services.file_share_service import check_file_access

logger = logging.getLogger("v2.file_derivatives")

STANDARD_IMAGE_KIND = "standard_image"
STANDARD_IMAGE_MIME = "image/jpeg"
STANDARD_IMAGE_EXTENSION = "jpg"
SUPPORTED_IMAGE_EXTENSIONS = {
    "jpg", "jpeg", "jpe", "jfif", "png", "webp", "bmp", "gif", "ico",
    "tif", "tiff", "avif",
}
SUPPORTED_IMAGE_MIME_PREFIX = "image/"
MAX_STANDARD_IMAGE_SIDE = 4096
STANDARD_IMAGE_QUALITY = 92


def _upload_root() -> Path:
    return Path(get_settings().UPLOAD_DIR).resolve()


def _safe_storage_path(storage_path: str) -> Path | None:
    if not storage_path:
        return None
    upload_root = _upload_root()
    full_path = (upload_root / storage_path).resolve()
    if os.path.commonpath([str(upload_root), str(full_path)]) != str(upload_root):
        return None
    return full_path if full_path.is_file() else None


def is_standardizable_image(file: File) -> bool:
    ext = (file.extension or "").lower()
    mime_type = (file.mime_type or "").lower()
    if ext == "svg" or mime_type == "image/svg+xml":
        return False
    return ext in SUPPORTED_IMAGE_EXTENSIONS or mime_type.startswith(SUPPORTED_IMAGE_MIME_PREFIX)


async def ensure_standard_image_derivative(db: AsyncSession, file_id: int) -> FileDerivative | None:
    file = await db.get(File, file_id)
    if not file or file.deleted:
        return None
    if not is_standardizable_image(file):
        return None

    existing = await _get_current_derivative(db, file)
    if existing:
        return existing

    source_path = _safe_storage_path(file.storage_path)
    if not source_path:
        return None

    try:
        derivative = _build_standard_image_derivative(file, source_path)
    except Exception as exc:
        logger.warning("Failed to build standard image derivative for file_id=%s: %s", file_id, exc)
        return None

    db.add(derivative)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        logger.exception("Failed to persist standard image derivative for file_id=%s", file_id)
        return None
    await db.refresh(derivative)
    return derivative


async def get_standard_image_derivative(db: AsyncSession, file_id: int) -> FileDerivative | None:
    file = await db.get(File, file_id)
    if not file or file.deleted:
        raise NotFound("File not found")
    if not is_standardizable_image(file):
        return None
    existing = await _get_current_derivative(db, file)
    if existing:
        return existing
    return await ensure_standard_image_derivative(db, file_id)


async def resolve_standard_image_path_for_user(
    db: AsyncSession,
    file_id: int,
    user_id: int,
) -> tuple[File, Path, str, str] | None:
    access = await check_file_access(db, file_id, user_id)
    if not access["accessible"]:
        raise PermissionDenied("Permission denied")
    file = await db.get(File, file_id)
    if not file or file.deleted:
        raise NotFound("File not found")
    derivative = await get_standard_image_derivative(db, file_id)
    if not derivative:
        return None
    path = _safe_storage_path(derivative.storage_path)
    if not path:
        return None
    return file, path, STANDARD_IMAGE_EXTENSION, derivative.mime_type


async def resolve_image_source_for_processing(
    db: AsyncSession,
    file_id: int,
    user_id: int,
) -> tuple[File, Path, str, str]:
    resolved = await resolve_standard_image_path_for_user(db, file_id, user_id)
    if resolved:
        return resolved
    access = await check_file_access(db, file_id, user_id)
    if not access["accessible"]:
        raise PermissionDenied("Permission denied")
    file = await db.get(File, file_id)
    if not file or file.deleted:
        raise NotFound("File not found")
    if not is_standardizable_image(file):
        raise ValidationError("file_id must point to an image file")
    path = _safe_storage_path(file.storage_path)
    if not path:
        raise NotFound("Image file on disk not found")
    return file, path, (file.extension or "").lower(), file.mime_type or "application/octet-stream"


async def _get_current_derivative(db: AsyncSession, file: File) -> FileDerivative | None:
    result = await db.execute(
        select(FileDerivative)
        .where(
            FileDerivative.file_id == file.id,
            FileDerivative.kind == STANDARD_IMAGE_KIND,
            FileDerivative.source_md5_hash == file.md5_hash,
        )
        .order_by(FileDerivative.id.desc())
        .limit(1)
    )
    derivative = result.scalar_one_or_none()
    if derivative and _safe_storage_path(derivative.storage_path):
        return derivative
    return None


def _build_standard_image_derivative(file: File, source_path: Path) -> FileDerivative:
    from PIL import Image, ImageOps

    source_bytes = source_path.read_bytes()
    source_md5 = file.md5_hash or hashlib.md5(source_bytes).hexdigest()
    with allow_large_image_decode(Image):
        with Image.open(io.BytesIO(source_bytes)) as image:
            working = ImageOps.exif_transpose(image)
            if getattr(working, "is_animated", False):
                working.seek(0)
            working = working.copy()

    if max(working.size) > MAX_STANDARD_IMAGE_SIDE:
        working.thumbnail((MAX_STANDARD_IMAGE_SIDE, MAX_STANDARD_IMAGE_SIDE), Image.Resampling.LANCZOS)

    if working.mode in {"RGBA", "LA"} or (working.mode == "P" and "transparency" in working.info):
        background = Image.new("RGB", working.size, (255, 255, 255))
        rgba = working.convert("RGBA")
        background.paste(rgba, mask=rgba.getchannel("A"))
        working = background
    elif working.mode != "RGB":
        working = working.convert("RGB")

    out = io.BytesIO()
    working.save(out, format="JPEG", quality=STANDARD_IMAGE_QUALITY, optimize=True)
    data = out.getvalue()
    md5_hash = hashlib.md5(data).hexdigest()
    storage_path = f"derivatives/{file.id}/{md5_hash}.{STANDARD_IMAGE_EXTENSION}"
    target_path = _upload_root() / storage_path
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_bytes(data)

    return FileDerivative(
        file_id=file.id,
        kind=STANDARD_IMAGE_KIND,
        storage_path=storage_path,
        mime_type=STANDARD_IMAGE_MIME,
        size=len(data),
        md5_hash=md5_hash,
        width=working.width,
        height=working.height,
        source_md5_hash=source_md5,
        metadata_json={
            "version": "standard_image_v1",
            "source_storage_path": file.storage_path,
            "source_mime_type": file.mime_type,
            "source_extension": file.extension,
            "quality": STANDARD_IMAGE_QUALITY,
            "max_side": MAX_STANDARD_IMAGE_SIDE,
        },
    )
