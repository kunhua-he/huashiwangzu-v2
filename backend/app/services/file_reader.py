"""Common file read entry for parser modules.

Replaces the 5-way copy of _resolve_user_id(), check_file_access + storage_path
+ commonpath boilerplate.  Parser modules call read_uploaded_file() instead of
hand-writing their own file-open preamble.
"""
import os
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import get_settings
from app.core.exceptions import NotFound, ValidationError, AppException, PermissionDenied


def resolve_caller_user_id(caller: str) -> int:
    try:
        prefix, raw_id = caller.split(":", 1)
        if prefix == "user":
            return int(raw_id)
    except (TypeError, ValueError):
        pass
    raise PermissionDenied("Invalid caller")


async def read_uploaded_file(
    db: AsyncSession,
    file_id: int,
    user_id: int,
    allowed_exts: set[str],
) -> tuple:
    """Resolve file_id → (File ORM row, resolved Path on disk).

    Combines check_file_access + extension validation + storage_path
    resolution + path-traversal guard into one call.
    """
    from app.services.file_service import check_file_access
    from app.models.file import File

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
    return file, full_path
