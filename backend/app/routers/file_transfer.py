import io
import json
import logging
import os
import tempfile
import hashlib
import uuid
import zipfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from fastapi import APIRouter, Depends, UploadFile, File as FastAPIFile, Form
from fastapi.responses import StreamingResponse, FileResponse
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exceptions import NotFound, PermissionDenied, ValidationError
from app.database import get_db
from app.schemas.common import ApiResponse
from app.schemas.file import UploadResponse
from app.middleware.auth import require_permission
from app.models.user import User
from app.models.file_upload_session import FileUploadSession
from app.services import file_upload_service, file_preview_service, file_service
from app.services import file_share_service
from app.config import get_settings

logger = logging.getLogger("v2.file_transfer")

MAX_UPLOAD_BYTES = 200 * 1024 * 1024  # 200MB 上传上限，防 OOM
CHUNK_SIZE = 1 * 1024 * 1024  # 1MB per chunk

router = APIRouter(prefix="/api/files", tags=["files"])


# ── Chunked Upload: Session Status ─────────────────────────────────

@router.get("/upload/{session_id}")
async def upload_session_status(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("viewer")),
):
    """Return current status of a chunked upload session (for resume)."""
    r = await db.execute(
        select(FileUploadSession).where(
            FileUploadSession.session_id == session_id,
            FileUploadSession.owner_id == user.id,
            FileUploadSession.deleted == False,
        )
    )
    session = r.scalar_one_or_none()
    if not session:
        raise NotFound("Upload session not found")

    now = datetime.now(timezone.utc)
    expired = now > session.expires_at.replace(tzinfo=timezone.utc) if session.expires_at.tzinfo is None else now > session.expires_at

    return ApiResponse(data={
        "session_id": session.session_id,
        "filename": session.filename,
        "total_chunks": session.total_chunks,
        "received_chunks": session.received_chunks,
        "status": "expired" if expired else session.status,
        "expired": expired,
        "expires_at": session.expires_at.isoformat(),
        "created_at": session.created_at.isoformat() if hasattr(session, 'created_at') else None,
    })


def _check_session_expired(session: FileUploadSession) -> bool:
    """Return True if session has expired."""
    now = datetime.now(timezone.utc)
    expires = session.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    return now > expires


# ── Chunked Upload: Init ───────────────────────────────────────────

@router.post("/upload/init")
async def upload_init(
    filename: str = Form(...),
    total_chunks: int = Form(...),
    md5_expected: str = Form(""),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("editor")),
):
    if total_chunks <= 0:
        raise ValidationError("total_chunks must be > 0")
    if total_chunks * CHUNK_SIZE > MAX_UPLOAD_BYTES:
        raise ValidationError(f"Total upload size exceeds {MAX_UPLOAD_BYTES // (1024*1024)}MB limit")

    session_id = str(uuid.uuid4())
    temp_dir = Path(get_settings().UPLOAD_DIR).resolve().parent / ".chunked_uploads" / session_id
    temp_dir.mkdir(parents=True, exist_ok=True)

    session = FileUploadSession(
        session_id=session_id,
        filename=filename,
        total_chunks=total_chunks,
        received_chunks=0,
        md5_expected=md5_expected or None,
        status="pending",
        temp_dir=str(temp_dir),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        owner_id=user.id,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)

    return ApiResponse(data={
        "session_id": session_id,
        "total_chunks": total_chunks,
        "chunk_size": CHUNK_SIZE,
        "expires_at": session.expires_at.isoformat(),
    })


# ── Chunked Upload: Complete (merge + md5 verify + content-addressable store + event) ──
# NOTE: placed BEFORE the variable-chunk-index route so "complete" is not parsed as an int

@router.post("/upload/{session_id}/complete")
async def upload_complete(
    session_id: str,
    folder_id: int = Form(0),
    relative_path: str = Form(""),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("editor")),
):
    r = await db.execute(
        select(FileUploadSession).where(
            FileUploadSession.session_id == session_id,
            FileUploadSession.owner_id == user.id,
            FileUploadSession.deleted == False,
        )
    )
    session = r.scalar_one_or_none()
    if not session:
        raise NotFound("Upload session not found")
    if _check_session_expired(session):
        session.status = "failed"
        await db.commit()
        raise ValidationError("Upload session has expired")
    if session.status == "completed":
        raise ValidationError("Upload session already completed")
    if session.received_chunks != session.total_chunks:
        raise ValidationError(
            f"Incomplete upload: {session.received_chunks}/{session.total_chunks} chunks received"
        )

    # Merge chunks into a temp file, calculating md5
    tmp_dir = Path(get_settings().UPLOAD_DIR).resolve().parent / ".tmp_uploads"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_fd, tmp_path = tempfile.mkstemp(dir=str(tmp_dir))
    md5 = hashlib.md5()
    total_size = 0
    try:
        for idx in range(session.total_chunks):
            chunk_path = Path(session.temp_dir) / f"{idx:06d}"
            if not chunk_path.exists():
                raise ValidationError(f"Missing chunk {idx}")
            data = chunk_path.read_bytes()
            os.write(tmp_fd, data)
            md5.update(data)
            total_size += len(data)
    finally:
        os.close(tmp_fd)

    merged_md5 = md5.hexdigest()

    # Verify expected md5 if provided
    if session.md5_expected and session.md5_expected != merged_md5:
        session.status = "failed"
        await db.commit()
        Path(tmp_path).unlink(missing_ok=True)
        raise ValidationError(
            f"MD5 mismatch: expected={session.md5_expected} actual={merged_md5}"
        )

    # Content-addressable store via existing service
    tmp_file_path = Path(tmp_path)
    from app.services.file_upload_service import _detect_mime_by_header
    mime_type = _detect_mime_by_header(tmp_file_path, session.filename)
    target_folder = folder_id if folder_id > 0 else None
    rp = relative_path.strip() if relative_path else None

    result = await file_upload_service.upload_file_from_path(
        db, tmp_file_path, session.filename, user.id, target_folder, rp,
        md5_hex=merged_md5, mime_type=mime_type,
    )

    # Cleanup temp files
    tmp_file_path.unlink(missing_ok=True)
    import shutil
    shutil.rmtree(Path(session.temp_dir), ignore_errors=True)

    session.status = "completed"
    await db.commit()

    # ── Emit file.uploaded event ──
    try:
        from app.services.module_events import emit_module_event
        await emit_module_event(
            "file.uploaded",
            {"file_id": result["id"]},
            caller=f"user:{user.id}",
            caller_role=user.role,
        )
    except Exception as exc:
        logger.warning("File.uploaded event emission failed for file_id=%d: %s", result["id"], exc)

    return ApiResponse(data={
        **UploadResponse(**result).model_dump(),
        "session_id": session_id,
        "chunks_merged": session.total_chunks,
        "md5": merged_md5,
    })


# ── Chunked Upload: Upload Chunk ───────────────────────────────────

@router.post("/upload/{session_id}/{chunk_index}")
async def upload_chunk(
    session_id: str,
    chunk_index: int,
    chunk: UploadFile = FastAPIFile(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("editor")),
):
    r = await db.execute(
        select(FileUploadSession).where(
            FileUploadSession.session_id == session_id,
            FileUploadSession.owner_id == user.id,
            FileUploadSession.deleted == False,
        )
    )
    session = r.scalar_one_or_none()
    if not session:
        raise NotFound("Upload session not found")
    if _check_session_expired(session):
        raise ValidationError("Upload session has expired")
    if session.status == "completed":
        raise ValidationError("Upload session already completed")
    if session.status == "failed":
        raise ValidationError("Upload session is in failed state")
    if chunk_index < 0 or chunk_index >= session.total_chunks:
        raise ValidationError(f"chunk_index out of range (0-{session.total_chunks - 1})")

    session.status = "uploading"
    chunk_data = await chunk.read()
    if len(chunk_data) == 0:
        raise ValidationError("Empty chunk")
    if len(chunk_data) > CHUNK_SIZE:
        raise ValidationError(f"Chunk exceeds {CHUNK_SIZE // 1024}KB limit")

    chunk_path = Path(session.temp_dir) / f"{chunk_index:06d}"
    chunk_path.write_bytes(chunk_data)

    received = len(list(Path(session.temp_dir).iterdir()))
    session.received_chunks = received
    await db.commit()

    return ApiResponse(data={
        "session_id": session_id,
        "chunk_index": chunk_index,
        "received_chunks": received,
        "total_chunks": session.total_chunks,
    })


# ── Legacy single-shot upload (kept for backward compatibility) ────

@router.post("/upload")
async def upload(file: UploadFile = FastAPIFile(...), folder_id: int = Form(0), relative_path: str = Form(""), db: AsyncSession = Depends(get_db), user: User = Depends(require_permission("editor"))):
    if not file.filename:
        raise ValidationError("No file provided")
    # 流式写入临时文件，同时计算 md5
    tmp_dir = Path(get_settings().UPLOAD_DIR).resolve().parent / ".tmp_uploads"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_fd, tmp_path = tempfile.mkstemp(dir=str(tmp_dir))
    total = 0
    md5 = hashlib.md5()
    try:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_UPLOAD_BYTES:
                raise ValidationError(f"文件过大，超过 {MAX_UPLOAD_BYTES // (1024*1024)}MB 限制")
            os.write(tmp_fd, chunk)
            md5.update(chunk)
        if total == 0:
            raise ValidationError("Empty file")
    finally:
        os.close(tmp_fd)
    tmp_file_path = Path(tmp_path)
    md5_hex = md5.hexdigest()
    rp = relative_path.strip() if relative_path else None
    target_folder = folder_id if folder_id > 0 else None
    from app.services.file_upload_service import _detect_mime_by_header
    mime_type = _detect_mime_by_header(tmp_file_path, file.filename)
    result = await file_upload_service.upload_file_from_path(
        db, tmp_file_path, file.filename, user.id, target_folder, rp,
        md5_hex=md5_hex, mime_type=mime_type,
    )
    # Temp file cleanup
    try:
        tmp_file_path.unlink(missing_ok=True)
    except Exception:
        pass
    # ── 上传完成，尽力而为通知各模块（不阻塞上传） ──
    try:
        from app.services.module_events import emit_module_event
        await emit_module_event(
            "file.uploaded",
            {"file_id": result["id"]},
            caller=f"user:{user.id}",
            caller_role=user.role,
        )
    except Exception as exc:
        logger.warning("File.uploaded event emission failed for file_id=%d: %s", result["id"], exc)
    return ApiResponse(data=UploadResponse(**result))


@router.get("/download/{file_id}")
async def download(file_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(require_permission("viewer"))):
    file = await file_service.get_file_record(db, file_id)
    if not file:
        raise NotFound("File not found")
    access = await file_share_service.check_file_access(db, file_id, user.id)
    if not access["accessible"]:
        raise PermissionDenied("Permission denied")
    safe_path = file_preview_service._resolve_storage_path(file)
    if not safe_path:
        raise NotFound("File on disk not found")
    full_name = f"{file.name}.{file.extension}" if file.extension else file.name
    return FileResponse(path=str(safe_path), media_type=file.mime_type or "application/octet-stream", filename=full_name)


@router.post("/download-multiple")
async def download_multiple(file_ids: list[int], db: AsyncSession = Depends(get_db), user: User = Depends(require_permission("viewer"))):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for fid in file_ids:
            file = await file_service.get_file_record(db, fid)
            if not file:
                continue
            access = await file_share_service.check_file_access(db, fid, user.id)
            if not access["accessible"]:
                continue
            safe_path = file_preview_service._resolve_storage_path(file)
            if not safe_path:
                continue
            arcname = f"{file.name}.{file.extension}" if file.extension else file.name
            zf.write(str(safe_path), arcname=arcname)
    buf.seek(0)
    return StreamingResponse(content=buf, media_type="application/zip", headers={"Content-Disposition": "attachment; filename=files.zip"})


@router.get("/preview/{file_id}")
async def preview(file_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(require_permission("viewer"))):
    result = await file_preview_service.preview_file(db, file_id, user.id)
    return ApiResponse(data=result)
