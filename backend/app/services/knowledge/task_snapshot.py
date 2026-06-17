import json
from datetime import datetime, timezone

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import Catalog, KnowledgeTask

API_STATUS_MAP = {"processing": "running"}


def _api_status(status: str) -> str:
    return API_STATUS_MAP.get(status, status)


def _progress(task: KnowledgeTask) -> dict:
    api_status = _api_status(task.status)
    return {
        "percent": task.progress or 0,
        "current_step": task.task_type,
        "chunk_count": 0,
        "candidate_count": 0,
        "evidence_count": 0,
        "phase_list": [{"name": task.task_type, "status": api_status}],
    }


def _task_item(task: KnowledgeTask, catalog: Catalog | None) -> dict:
    created = task.created_at.isoformat() if task.created_at else ""
    api_status = _api_status(task.status)
    return {
        "task_id": task.id,
        "file_id": task.catalog_id,
        "file_name": catalog.file_name if catalog else None,
        "channel": catalog.channel_type if catalog else None,
        "priority": 0,
        "status": api_status,
        "enqueued_at": created,
        "started_at": task.heartbeat.isoformat() if task.heartbeat else None,
        "ended_at": task.updated_at.isoformat() if task.status in {"done", "failed"} and task.updated_at else None,
        "error_message": task.error,
        "progress": _progress(task),
    }


async def build_task_snapshot(db: AsyncSession) -> dict:
    result = await db.execute(select(KnowledgeTask).order_by(desc(KnowledgeTask.id)).limit(50))
    tasks = result.scalars().all()
    catalog_ids = {task.catalog_id for task in tasks}
    catalogs: dict[int, Catalog] = {}
    if catalog_ids:
        catalog_result = await db.execute(select(Catalog).where(Catalog.id.in_(catalog_ids)))
        catalogs = {catalog.id: catalog for catalog in catalog_result.scalars().all()}
    items = [_task_item(task, catalogs.get(task.catalog_id)) for task in tasks]
    now = datetime.now(timezone.utc).isoformat()
    active = [item for item in items if item["status"] in {"pending", "running"}]
    realtime = [{
        "time": now,
        "file_id": item["file_id"],
        "file_name": item["file_name"] or f"File {item['file_id']}",
        "status": item["status"],
        "current_step": item["progress"]["current_step"],
        "percent": item["progress"]["percent"],
    } for item in active[:20]]
    return {"task_list": items, "recent_logs": realtime}


def sse_payload(snapshot: dict) -> str:
    return "data: " + json.dumps(snapshot, ensure_ascii=False) + "\n\n"
