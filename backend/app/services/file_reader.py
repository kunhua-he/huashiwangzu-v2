"""Shared file access helpers for parser and file-aware modules."""
import os
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.exceptions import AppException, NotFound, PermissionDenied, ValidationError


def resolve_caller_user_id(caller: str) -> int:
    """Extract user ID from caller string.

    Accepted formats:
        user:{id} — normal user
        system:* — system principal (returns 0, owner-sensitive operations must reject)

    Raises PermissionDenied for invalid format.
    """
    try:
        prefix, raw_id = caller.split(":", 1)
        if prefix == "user":
            return int(raw_id)
        if prefix == "system":
            return 0  # System principal; caller must check owner_id before write
    except (TypeError, ValueError):
        pass
    raise PermissionDenied("Invalid caller")


def is_system_caller(caller: str) -> bool:
    """Check if the caller is a system principal (not tied to a user)."""
    try:
        prefix, _ = caller.split(":", 1)
        return prefix == "system"
    except (TypeError, ValueError):
        return False


def require_positive_file_id(params: dict) -> int:
    file_id = int(params.get("file_id", 0))
    if file_id <= 0:
        raise ValueError("file_id must be a positive integer")
    return file_id


async def read_uploaded_file(
    db: AsyncSession,
    file_id: int,
    user_id: int,
    allowed_exts: set[str],
) -> tuple[object, Path, str]:
    """Resolve file_id into the ORM row, resolved path, and file extension.

    Combines check_file_access + extension validation + storage_path
    resolution + path-traversal guard into one call.
    """
    from app.services.file_service import check_file_access

    file = await check_file_access(db, file_id, user_id)
    ext = (file.extension or "").lower()
    if ext not in allowed_exts:
        raise ValidationError(
            f"Unsupported format '{ext}'. Allowed: {', '.join(sorted(allowed_exts))}"
        )
    if not file.storage_path:
        raise NotFound("File storage path is empty")
    upload_root = Path(get_settings().UPLOAD_DIR).resolve()
    full_path = (upload_root / file.storage_path).resolve()
    if os.path.commonpath([str(upload_root), str(full_path)]) != str(upload_root):
        raise AppException("Unsafe file storage path", status_code=400)
    if not full_path.exists() or not full_path.is_file():
        raise NotFound("File on disk not found")
    if _is_image_file(ext, file.mime_type):
        from app.services.image_derivative_service import resolve_standard_image_path_for_user

        derivative = await resolve_standard_image_path_for_user(db, file_id, user_id)
        if derivative:
            file, derivative_path, derivative_ext, _mime_type = derivative
            return file, derivative_path, derivative_ext
    return file, full_path, ext


def _is_image_file(ext: str, mime_type: str | None) -> bool:
    image_exts = {"jpg", "jpeg", "jpe", "jfif", "png", "gif", "webp", "bmp", "ico", "tif", "tiff", "avif"}
    mime = (mime_type or "").lower()
    if mime == "image/svg+xml":
        return True
    return ext.lower() in image_exts or mime.startswith("image/")


def decode_text_bytes(raw: bytes) -> str:
    encodings = ["utf-8", "utf-8-sig", "gbk", "gb2312", "latin-1"]
    for enc in encodings:
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("utf-8", errors="replace")


async def get_file_content_bytes(file_id: int, user_id: int) -> bytes:
    """Read the raw bytes of a file from disk by file_id and owner_id.

    Returns the raw file content bytes. Access-controlled via check_file_access.
    """
    from pathlib import Path

    from app.config import get_settings
    from app.database import AsyncSessionLocal
    from app.services.file_service import check_file_access

    async with AsyncSessionLocal() as db:
        file = await check_file_access(db, file_id, user_id)
        if not file.storage_path:
            raise NotFound("File storage path is empty")
        upload_root = Path(get_settings().UPLOAD_DIR).resolve()
        full_path = (upload_root / file.storage_path).resolve()
        if os.path.commonpath([str(upload_root), str(full_path)]) != str(upload_root):
            raise AppException("Unsafe file path", status_code=400)
        if not full_path.exists() or not full_path.is_file():
            raise NotFound("File not found on disk")
        return full_path.read_bytes()
