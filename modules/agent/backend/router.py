import json
import logging
import sys
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("v2.agent.router")

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.gateway.router import gateway_router
from app.middleware.auth import require_permission
from app.models.user import User
from app.schemas.common import ApiResponse

MODULE_BACKEND_DIR = Path(__file__).resolve().parent
if str(MODULE_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_BACKEND_DIR))

from action_policy import check_action_allowed, resolve_approval, list_pending_approvals
import conversation_service as conv_svc
from init_db import ensure_default_prompts, ensure_timeline_column, ensure_user_profile, update_existing_prompts, ensure_event_table, ensure_processing_column
from model_client import recover_tool_calls, parse_inline_tool_calls, final_clean_content
import tool_discovery
from profile_evolve import handle_profile_evolve
ENGINE_DIR = (MODULE_BACKEND_DIR / ".." / "engine").resolve()
if str(ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(ENGINE_DIR))
import 事件存储
from 事件存储 import record_event
import 引擎
from 引擎 import 装配上下文, chat_with_degradation_chain, chat_stream_with_degradation_chain
from 粘滞检测 import 检测粘滞, 重置 as 重置粘滞

router = APIRouter(prefix="/api/agent", tags=["agent"])

# 注册后台任务处理器（框架 worker 自动消费）
from .handlers import tasks  # noqa: F401 — triggers register_task_handler calls


def _j(obj) -> str:
    """json.dumps with datetime fallback."""
    return json.dumps(obj, ensure_ascii=False, default=str)


def _conversation_payload(item) -> dict:
    return {"id": item.id, "title": item.title, "status": item.status}


# ── Request Schemas ──

class CreateConvRequest(BaseModel):
    title: str = "新对话"


class RenameConvRequest(BaseModel):
    title: str


class ChatRequest(BaseModel):
    conversation_id: int
    content: str
    profile_key: str | None = None


class UpdatePromptRequest(BaseModel):
    content: str


class ApprovalDecision(BaseModel):
    decision: str  # "approved" | "rejected"
    reason: str | None = None


# ── Health / Profiles / Tools ──

@router.get("/health")
async def health():
    return ApiResponse(data={"module": "agent", "status": "ok"})


@router.get("/profiles")
async def list_profiles(user: User = Depends(require_permission("viewer"))):
    return ApiResponse(data=gateway_router.list_profiles())


@router.get("/tools")
async def list_tools(user: User = Depends(require_permission("viewer"))):
    tools = tool_discovery.build_tools(user.role)
    return ApiResponse(data=tools)


# ── 三层提示词管理接口 ──

@router.get("/system-prompt")
async def get_system_prompt(db: AsyncSession = Depends(get_db), user: User = Depends(require_permission("viewer"))):
    """获取当前系统提示词内容（只读，所有人可看）。"""
    content = await conv_svc.get_system_prompt(db)
    return ApiResponse(data={"content": content})


@router.put("/system-prompt")
async def update_system_prompt(
    payload: UpdatePromptRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("admin")),
):
    """管理员更新系统提示词。"""
    prompt = await conv_svc.update_system_prompt(db, payload.content, user.id)
    return ApiResponse(data={"id": prompt.id, "content": prompt.content, "version": prompt.version})


@router.get("/enterprise-prompt")
async def get_enterprise_prompt(db: AsyncSession = Depends(get_db), user: User = Depends(require_permission("viewer"))):
    """获取当前企业提示词内容。"""
    content = await conv_svc.get_enterprise_prompt(db)
    return ApiResponse(data={"content": content})


@router.put("/enterprise-prompt")
async def update_enterprise_prompt(
    payload: UpdatePromptRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("admin")),
):
    """管理员更新企业提示词。"""
    prompt = await conv_svc.update_enterprise_prompt(db, payload.content, user.id)
    return ApiResponse(data={"id": prompt.id, "content": prompt.content, "version": prompt.version})


@router.get("/user-profile")
async def get_my_profile(db: AsyncSession = Depends(get_db), user: User = Depends(require_permission("viewer"))):
    """获取当前用户的个人画像。"""
    from init_db import ensure_user_profile
    profile = await ensure_user_profile(db, user.id)
    return ApiResponse(data={
        "owner_id": profile.owner_id,
        "profile_data": json.loads(profile.profile_data) if profile.profile_data else {},
        "version": profile.version,
        "evolved_at": profile.evolved_at.isoformat() if profile.evolved_at else None,
        "conversation_count": profile.conversation_count,
    })


# ── 对话接口 ──

@router.get("/conversations")
async def list_conversations(db: AsyncSession = Depends(get_db), user: User = Depends(require_permission("viewer"))):
    items = await conv_svc.list_conversations(db, user.id)
    return ApiResponse(data=[_conversation_payload(item) for item in items])


@router.post("/conversations")
async def create_conversation(payload: CreateConvRequest, db: AsyncSession = Depends(get_db), user: User = Depends(require_permission("viewer"))):
    await ensure_processing_column(db)
    await ensure_event_table(db)
    item = await conv_svc.create_conversation(db, user.id, payload.title)
    return ApiResponse(data=_conversation_payload(item))


@router.patch("/conversations/{conversation_id}")
async def rename_conversation(
    conversation_id: int,
    payload: RenameConvRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("viewer")),
):
    item = await conv_svc.rename_conversation(db, user.id, conversation_id, payload.title)
    return ApiResponse(data=_conversation_payload(item) if item else None)


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(require_permission("viewer"))):
    return ApiResponse(data={"deleted": await conv_svc.delete_conversation(db, user.id, conversation_id)})


@router.get("/conversations/{conversation_id}/messages")
async def get_messages(conversation_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(require_permission("viewer"))):
    return ApiResponse(data=await conv_svc.get_messages_with_meta(db, user.id, conversation_id))


# ── 聊天 ──

@router.post("/chat")
async def chat(payload: ChatRequest, db: AsyncSession = Depends(get_db), user: User = Depends(require_permission("viewer"))):
    from .handlers.chat import handle_chat
    return await handle_chat(payload, db, user)


# ── 引擎批5：Admin 只读接口（重放 + 概览） ──

@router.get("/admin/replay/{conversation_id}")
async def admin_replay(
    conversation_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("admin")),
):
    from .handlers.admin import handle_admin_replay
    return await handle_admin_replay(conversation_id, db, user)


@router.get("/admin/overview")
async def admin_overview(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("admin")),
):
    from .handlers.admin import handle_admin_overview
    return await handle_admin_overview(db, user)


# ── 敏感操作审批 API ──

@router.get("/admin/approvals/pending")
async def list_approvals(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("admin")),
):
    from .handlers.admin import handle_list_approvals
    return await handle_list_approvals(db, user)


@router.post("/admin/approvals/{approval_id}/resolve")
async def resolve_approval_endpoint(
    approval_id: int,
    body: ApprovalDecision,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("admin")),
):
    from .handlers.admin import handle_resolve_approval
    return await handle_resolve_approval(approval_id, body.decision, body.reason, db, user)


# Import capabilities to register them at module load
# noinspection PyUnresolvedReferences
from .handlers import tool  # noqa: F401, E402
