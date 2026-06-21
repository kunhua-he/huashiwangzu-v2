import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, AsyncSessionLocal
from app.middleware.auth import require_permission
from app.models.user import User
from app.schemas.common import ApiResponse
from app.services.module_registry import register_capability

logger = logging.getLogger("v2.memory.router")

from huashiwangzu_modules.memory.models import AgentMemory
from huashiwangzu_modules.memory.init_db import run_init

router = APIRouter(prefix="/api/memory", tags=["memory"])


class SaveMemoryRequest(BaseModel):
    text: str
    tags: str | None = None


class RecallRequest(BaseModel):
    query: str
    limit: int = 5


class DeleteMemoryRequest(BaseModel):
    id: int


async def _ensure_init() -> None:
    await run_init()


def _parse_user_id(caller: str) -> int:
    if caller and caller.startswith("user:"):
        return int(caller.split(":", 1)[1])
    return 0


@router.post("/save")
async def http_save(
    req: SaveMemoryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("viewer")),
):
    await _ensure_init()
    if not req.text.strip():
        return ApiResponse(success=False, error="内容不能为空")
    memory = AgentMemory(
        owner_id=current_user.id,
        text=req.text,
        tags=req.tags if req.tags else None,
    )
    db.add(memory)
    await db.commit()
    await db.refresh(memory)
    return ApiResponse(data={"id": memory.id, "status": "saved"})


@router.post("/recall")
async def http_recall(
    req: RecallRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("viewer")),
):
    await _ensure_init()
    keyword = f"%{req.query}%"
    stmt = (
        select(AgentMemory)
        .where(
            AgentMemory.owner_id == current_user.id,
            or_(
                AgentMemory.text.ilike(keyword),
                AgentMemory.tags.ilike(keyword),
            ),
        )
        .order_by(AgentMemory.id.desc())
        .limit(req.limit)
    )
    r = await db.execute(stmt)
    items = r.scalars().all()
    return ApiResponse(data=[{
        "id": m.id,
        "text": m.text,
        "tags": m.tags,
        "created_at": m.created_at.isoformat() if m.created_at else None,
    } for m in items])


@router.get("/list")
async def http_list(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("viewer")),
):
    await _ensure_init()
    stmt = (
        select(AgentMemory)
        .where(AgentMemory.owner_id == current_user.id)
        .order_by(AgentMemory.created_at.desc())
    )
    r = await db.execute(stmt)
    items = r.scalars().all()
    return ApiResponse(data=[{
        "id": m.id,
        "text": m.text,
        "tags": m.tags,
        "created_at": m.created_at.isoformat() if m.created_at else None,
    } for m in items])


@router.post("/delete")
async def http_delete(
    req: DeleteMemoryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("viewer")),
):
    await _ensure_init()
    memory = await db.get(AgentMemory, req.id)
    if not memory:
        return ApiResponse(success=False, error="记忆不存在")
    if memory.owner_id != current_user.id:
        return ApiResponse(success=False, error="只能删除自己的记忆")
    await db.delete(memory)
    await db.commit()
    return ApiResponse(data={"id": req.id, "status": "deleted"})


# ── Cross-module capabilities ──────────────────────────────────

async def _cap_save(params: dict, caller: str) -> dict:
    text = params.get("text", "")
    tags = params.get("tags")
    owner_id = _parse_user_id(caller)
    if not owner_id:
        return {"success": False, "error": "无法解析调用者身份"}
    if not text.strip():
        return {"success": False, "error": "内容不能为空"}
    await _ensure_init()
    async with AsyncSessionLocal() as db:
        memory = AgentMemory(owner_id=owner_id, text=text, tags=tags)
        db.add(memory)
        await db.commit()
        await db.refresh(memory)
    return {"success": True, "data": {"id": memory.id}}


async def _cap_recall(params: dict, caller: str) -> dict:
    query = params.get("query", "")
    limit = params.get("limit", 5)
    owner_id = _parse_user_id(caller)
    if not owner_id:
        return {"success": False, "error": "无法解析调用者身份"}
    await _ensure_init()
    keyword = f"%{query}%"
    async with AsyncSessionLocal() as db:
        stmt = (
            select(AgentMemory)
            .where(
                AgentMemory.owner_id == owner_id,
                or_(
                    AgentMemory.text.ilike(keyword),
                    AgentMemory.tags.ilike(keyword),
                ),
            )
            .order_by(AgentMemory.id.desc())
            .limit(limit)
        )
        r = await db.execute(stmt)
        items = r.scalars().all()
    return {"success": True, "data": [
        {"id": m.id, "text": m.text, "tags": m.tags,
         "created_at": m.created_at.isoformat() if m.created_at else None}
        for m in items
    ]}


async def _cap_list(params: dict, caller: str) -> dict:
    owner_id = _parse_user_id(caller)
    if not owner_id:
        return {"success": False, "error": "无法解析调用者身份"}
    await _ensure_init()
    async with AsyncSessionLocal() as db:
        stmt = (
            select(AgentMemory)
            .where(AgentMemory.owner_id == owner_id)
            .order_by(AgentMemory.created_at.desc())
        )
        r = await db.execute(stmt)
        items = r.scalars().all()
    return {"success": True, "data": [
        {"id": m.id, "text": m.text, "tags": m.tags,
         "created_at": m.created_at.isoformat() if m.created_at else None}
        for m in items
    ]}


async def _cap_delete(params: dict, caller: str) -> dict:
    mem_id = params.get("id")
    owner_id = _parse_user_id(caller)
    if not owner_id:
        return {"success": False, "error": "无法解析调用者身份"}
    await _ensure_init()
    async with AsyncSessionLocal() as db:
        memory = await db.get(AgentMemory, mem_id)
        if not memory:
            return {"success": False, "error": "记忆不存在"}
        if memory.owner_id != owner_id:
            return {"success": False, "error": "只能删除自己的记忆"}
        await db.delete(memory)
        await db.commit()
    return {"success": True, "data": {"id": mem_id, "status": "deleted"}}


register_capability(
    "memory", "save", _cap_save,
    description="保存一段记忆（笔记/事实），后续可检索回忆",
    brief="记一条备忘",
    parameters={
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "记忆内容"},
            "tags": {"type": "string", "description": "标签（可选，逗号分隔）"},
        },
        "required": ["text"],
    },
    min_role="viewer",
)

register_capability(
    "memory", "recall", _cap_recall,
    description="按关键词检索自己的记忆",
    brief="回忆我的备忘",
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "搜索关键词"},
            "limit": {"type": "integer", "description": "返回条数上限"},
        },
        "required": ["query"],
    },
    min_role="viewer",
)

register_capability(
    "memory", "list", _cap_list,
    description="列出自己所有的记忆",
    brief="列出所有备忘",
    parameters={"type": "object", "properties": {}},
    min_role="viewer",
)

register_capability(
    "memory", "delete", _cap_delete,
    description="删除一条记忆",
    brief="删除一条备忘",
    parameters={
        "type": "object",
        "properties": {"id": {"type": "integer", "description": "记忆 ID"}},
        "required": ["id"],
    },
    min_role="viewer",
)
