"""Knowledge reactions to framework file lifecycle events."""
import logging

from app.database import AsyncSessionLocal
from app.services.file_reader import resolve_caller_user_id
from app.services.module_events import register_module_event_handler
from sqlalchemy import select

from ..models import KbDocument
from .document_service import (
    document_pipeline_complete,
    enqueue_pipeline_task,
    mark_document_source_unavailable,
    register_document,
)
from .source_file_state import get_source_file_availability

logger = logging.getLogger("v2.knowledge").getChild("file_lifecycle")

SOURCE_UNAVAILABLE_REASONS = {"source_file_deleted", "source_file_missing"}


def _payload_file_id(payload: dict) -> int:
    return int(payload.get("file_id", 0) or 0)


def _payload_owner_id(payload: dict, caller: str) -> int:
    if payload.get("owner_id"):
        return int(payload["owner_id"])
    return resolve_caller_user_id(caller)


async def _on_file_deleted(payload: dict, caller: str, caller_role: str) -> dict:
    """Pause knowledge work for files that moved to recycle."""
    file_id = _payload_file_id(payload)
    if file_id <= 0:
        return {"skipped": True, "reason": "invalid file_id"}

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(KbDocument).where(
                KbDocument.file_id == file_id,
                KbDocument.deleted.is_(False),
            )
        )
        docs = result.scalars().all()
        for doc in docs:
            mark_document_source_unavailable(doc, "source_file_deleted")
        await db.commit()

    logger.info("Paused %d knowledge document(s) for deleted file_id=%d", len(docs), file_id)
    return {
        "file_id": file_id,
        "status": "skipped",
        "reason": "source_file_deleted",
        "documents_paused": len(docs),
    }


async def _on_file_restored(payload: dict, caller: str, caller_role: str) -> dict:
    """Resume or create knowledge pipeline work after a file is restored."""
    file_id = _payload_file_id(payload)
    if file_id <= 0:
        return {"skipped": True, "reason": "invalid file_id"}
    owner_id = _payload_owner_id(payload, caller)

    async with AsyncSessionLocal() as db:
        availability = await get_source_file_availability(db, file_id)
        if not availability.available:
            return {"file_id": file_id, "status": "skipped", "reason": availability.reason}

        result = await db.execute(
            select(KbDocument).where(
                KbDocument.file_id == file_id,
                KbDocument.owner_id == owner_id,
                KbDocument.deleted.is_(False),
            )
        )
        doc = result.scalar_one_or_none()
        if not doc:
            try:
                registered = await register_document(db, file_id, owner_id, catalog_id=None)
                return {
                    "file_id": file_id,
                    "document_id": registered["id"],
                    "status": "done",
                    "enqueued": True,
                    "reason": "registered_on_restore",
                }
            except Exception as exc:
                logger.info("Restore ingest skipped for file_id=%d: %s", file_id, exc)
                return {"file_id": file_id, "status": "skipped", "reason": str(exc)}

        if doc.parse_error in SOURCE_UNAVAILABLE_REASONS:
            doc.parse_error = None

        if document_pipeline_complete(doc):
            await db.commit()
            return {
                "file_id": file_id,
                "document_id": doc.id,
                "status": "skipped",
                "reason": "pipeline_already_done",
            }

        task_info = await enqueue_pipeline_task(
            db,
            doc,
            owner_id,
            force_raw=doc.raw_status != "done",
            force_fusion=doc.fusion_status != "done",
        )
        await db.commit()

    logger.info(
        "Resumed knowledge pipeline for restored file_id=%d document_id=%d enqueued=%s",
        file_id, doc.id, task_info.get("enqueued"),
    )
    return {
        "file_id": file_id,
        "document_id": doc.id,
        "status": "done",
        **task_info,
    }


register_module_event_handler("file.deleted", _on_file_deleted, "knowledge")
register_module_event_handler("file.restored", _on_file_restored, "knowledge")
