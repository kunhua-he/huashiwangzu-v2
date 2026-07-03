from __future__ import annotations

import hashlib
import logging
import os
import shutil
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.exceptions import NotFound, PermissionDenied, ValidationError
from app.models.file_upload_session import FileUploadSession
from app.services import file_upload_service

logger = logging.getLogger("v2.file_upload_session")

MAX_SESSION_UPLOAD_BYTES = 200 * 1024 * 1024
MAX_CHUNK_UPLOAD_BYTES = 64 * 1024 * 1024
MAX_TOTAL_CHUNKS = 10000


def _sessions_root() -> Path:
    return Path(get_settings().UPLOAD_DIR).resolve().parent / ".tmp_upload_sessions"


def _chunk_path(session: FileUploadSession, chunk_index: int) -> Path:
    return Path(session.temp_dir) / f"{chunk_index:08d}.part"


def _chunk_paths(session: FileUploadSession) -> list[Path]:
    return [_chunk_path(session, index) for index in range(session.total_chunks)]


def _clean_filename(filename: str) -> str:
    clean_name = filename.strip()
    if not clean_name:
        raise ValidationError("filename is required")
    if "/" in clean_name or "\\" in clean_name or Path(clean_name).name != clean_name:
        raise ValidationError("filename must not contain path separators")
    return clean_name


def _is_expired(session: FileUploadSession) -> bool:
    expires_at = session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at <= datetime.now(timezone.utc)


def _session_to_dict(session: FileUploadSession) -> dict:
    return {
        "session_id": session.session_id,
        "filename": session.filename,
        "total_chunks": session.total_chunks,
        "received_chunks": session.received_chunks,
        "status": session.status,
        "expires_at": session.expires_at,
    }


async def create_upload_session(
    db: AsyncSession,
    *,
    filename: str,
    total_chunks: int,
    owner_id: int,
    md5_expected: str | None = None,
    expires_in_hours: int = 24,
) -> dict:
    clean_name = _clean_filename(filename)
    if total_chunks < 1:
        raise ValidationError("total_chunks must be greater than 0")
    if total_chunks > MAX_TOTAL_CHUNKS:
        raise ValidationError("total_chunks exceeds the allowed maximum")
    if md5_expected and (len(md5_expected) != 32 or any(c not in "0123456789abcdefABCDEF" for c in md5_expected)):
        raise ValidationError("md5_expected must be a 32-character hex digest")
    expires_hours = min(max(expires_in_hours, 1), 168)

    session_id = str(uuid4())
    temp_dir = _sessions_root() / str(owner_id) / session_id
    temp_dir.mkdir(parents=True, exist_ok=False)

    session = FileUploadSession(
        session_id=session_id,
        filename=clean_name,
        total_chunks=total_chunks,
        received_chunks=0,
        md5_expected=md5_expected.lower() if md5_expected else None,
        status="pending",
        temp_dir=str(temp_dir),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=expires_hours),
        owner_id=owner_id,
        deleted=False,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return _session_to_dict(session)


async def get_upload_session(db: AsyncSession, session_id: str, owner_id: int) -> FileUploadSession:
    result = await db.execute(
        select(FileUploadSession).where(
            FileUploadSession.session_id == session_id,
            FileUploadSession.deleted.is_(False),
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise NotFound("Upload session not found")
    if session.owner_id != owner_id:
        raise PermissionDenied("Permission denied")
    if _is_expired(session):
        session.status = "expired"
        session.deleted = True
        await db.commit()
        shutil.rmtree(session.temp_dir, ignore_errors=True)
        raise ValidationError("Upload session expired")
    return session


async def store_upload_chunk(
    db: AsyncSession,
    *,
    session_id: str,
    owner_id: int,
    chunk_index: int,
    chunk_stream,
) -> dict:
    session = await get_upload_session(db, session_id, owner_id)
    if session.status in {"completed", "failed", "expired", "aborted"}:
        raise ValidationError(f"Upload session is {session.status}")
    if chunk_index < 0 or chunk_index >= session.total_chunks:
        raise ValidationError("chunk_index out of range")

    temp_dir = Path(session.temp_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)
    target = _chunk_path(session, chunk_index)
    fd, temp_name = tempfile.mkstemp(dir=str(temp_dir), prefix=f"{chunk_index:08d}.", suffix=".tmp")
    temp_path = Path(temp_name)
    written = 0
    try:
        while True:
            data = await chunk_stream.read(1024 * 1024)
            if not data:
                break
            written += len(data)
            if written > MAX_CHUNK_UPLOAD_BYTES:
                raise ValidationError(f"Chunk exceeds {MAX_CHUNK_UPLOAD_BYTES // (1024 * 1024)}MB limit")
            os.write(fd, data)
    except Exception:
        os.close(fd)
        temp_path.unlink(missing_ok=True)
        raise
    else:
        os.close(fd)
    if written == 0:
        temp_path.unlink(missing_ok=True)
        raise ValidationError("Empty chunk")

    os.replace(temp_name, target)
    session.received_chunks = sum(1 for path in _chunk_paths(session) if path.exists())
    session.status = "uploading" if session.received_chunks < session.total_chunks else "uploaded"
    await db.commit()
    await db.refresh(session)
    return _session_to_dict(session)


async def complete_upload_session(
    db: AsyncSession,
    *,
    session_id: str,
    owner_id: int,
    folder_id: int | None = None,
    relative_path: str | None = None,
) -> dict:
    session = await get_upload_session(db, session_id, owner_id)
    if session.status in {"completed", "failed", "expired", "aborted"}:
        raise ValidationError(f"Upload session is {session.status}")
    missing = [index for index, path in enumerate(_chunk_paths(session)) if not path.exists()]
    if missing:
        session.received_chunks = session.total_chunks - len(missing)
        session.status = "uploading" if session.received_chunks else "pending"
        await db.commit()
        raise ValidationError(f"Missing chunks: {missing[:10]}")

    temp_dir = Path(session.temp_dir)
    fd, assembled_name = tempfile.mkstemp(dir=str(temp_dir), prefix="assembled.", suffix=".upload")
    md5 = hashlib.md5()
    total = 0
    assembled_path = Path(assembled_name)
    try:
        try:
            for path in _chunk_paths(session):
                with path.open("rb") as chunk_file:
                    while True:
                        data = chunk_file.read(1024 * 1024)
                        if not data:
                            break
                        total += len(data)
                        if total > MAX_SESSION_UPLOAD_BYTES:
                            raise ValidationError(f"文件过大，超过 {MAX_SESSION_UPLOAD_BYTES // (1024 * 1024)}MB 限制")
                        os.write(fd, data)
                        md5.update(data)
        finally:
            os.close(fd)
    except Exception:
        assembled_path.unlink(missing_ok=True)
        raise
    md5_hex = md5.hexdigest()
    if session.md5_expected and session.md5_expected != md5_hex:
        assembled_path.unlink(missing_ok=True)
        session.status = "failed"
        await db.commit()
        raise ValidationError("MD5 mismatch")

    mime_type = file_upload_service._detect_mime_by_header(assembled_path, session.filename)
    try:
        uploaded = await file_upload_service.upload_file_from_path(
            db,
            assembled_path,
            session.filename,
            owner_id,
            folder_id if folder_id and folder_id > 0 else None,
            relative_path.strip() if relative_path else None,
            md5_hex=md5_hex,
            mime_type=mime_type,
        )
    except Exception:
        if assembled_path.exists():
            assembled_path.unlink(missing_ok=True)
        raise

    session.received_chunks = session.total_chunks
    session.status = "completed"
    await db.commit()
    await db.refresh(session)
    shutil.rmtree(session.temp_dir, ignore_errors=True)
    return {"session": _session_to_dict(session), "file": uploaded}


async def abort_upload_session(
    db: AsyncSession,
    *,
    session_id: str,
    owner_id: int,
) -> dict:
    session = await get_upload_session(db, session_id, owner_id)
    if session.status == "completed":
        raise ValidationError("Completed upload session cannot be aborted")
    session.status = "aborted"
    session.deleted = True
    await db.commit()
    await db.refresh(session)
    shutil.rmtree(session.temp_dir, ignore_errors=True)
    return _session_to_dict(session)


async def cleanup_expired_sessions(db: AsyncSession) -> dict:
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(FileUploadSession).where(
            FileUploadSession.deleted.is_(False),
            FileUploadSession.status != "completed",
            FileUploadSession.expires_at <= now,
        )
    )
    sessions = list(result.scalars().all())
    for session in sessions:
        try:
            shutil.rmtree(session.temp_dir, ignore_errors=True)
        except Exception as exc:
            logger.warning("Failed to remove upload session temp dir %s: %s", session.temp_dir, exc)
        session.status = "expired"
        session.deleted = True
    await db.commit()
    return {"cleaned": len(sessions)}
