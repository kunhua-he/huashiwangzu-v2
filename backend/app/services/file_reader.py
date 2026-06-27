"""Shared file access helpers for parser and file-aware modules."""
import os
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.exceptions import AppException, NotFound, PermissionDenied, ValidationError


def resolve_caller_user_id(caller: str) -> int:
    try:
        prefix, raw_id = caller.split(":", 1)
        if prefix == "user":
            return int(raw_id)
    except (TypeError, ValueError):
        pass
    raise PermissionDenied("Invalid caller")


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
    return file, full_path, ext


def decode_text_bytes(raw: bytes) -> str:
    encodings = ["utf-8", "utf-8-sig", "gbk", "gb2312", "latin-1"]
    for enc in encodings:
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("utf-8", errors="replace")
