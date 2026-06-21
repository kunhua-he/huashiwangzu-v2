import asyncio
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
from app.services.module_registry import call_capability, register_capability
from app.services.task_worker import register_task_handler

MODULE_BACKEND_DIR = Path(__file__).resolve().parent
if str(MODULE_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_BACKEND_DIR))

import conversation_service as conv_svc
from init_db import ensure_default_prompts, ensure_timeline_column, ensure_user_profile
from model_client import recover_tool_calls
import tool_discovery
from profile_evolve import handle_profile_evolve

# 注册后台任务处理器（框架 worker 自动消费）
register_task_handler("profile_evolve", handle_profile_evolve)

router = APIRouter(prefix="/api/agent", tags=["agent"])

MAX_TOOL_ROUNDS = 5
EVOLVE_EVERY_N_MESSAGES = 3  # 每 N 轮用户消息触发一次画像进化


def _j(obj) -> str:
    """json.dumps with datetime fallback."""
    return json.dumps(obj, ensure_ascii=False, default=str)


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


def _conversation_payload(item) -> dict:
    return {"id": item.id, "title": item.title, "status": item.status}


def _references_from_tool_events(events: list[dict]) -> list[dict]:
    refs: list[dict] = []
    for event in events:
        if event.get("type") != "tool_result":
            continue
        name = event.get("name", "tool") or ""
        result = event.get("result", {}) or {}
        # 知识库检索结果：提取文件名和页码作为结构化引用
        if "knowledge__search" in name:
            inner = result
            if isinstance(inner, dict) and "data" in inner:
                inner = inner["data"]
            results_list = []
            if isinstance(inner, dict):
                results_list = inner.get("results", [])
            elif isinstance(inner, list):
                results_list = inner
            for r_item in results_list:
                doc_name = r_item.get("document_name") or r_item.get("filename", "")
                page = r_item.get("page")
                excerpt = (r_item.get("text") or r_item.get("page_fusion", "") or "")[:240]
                title_parts = []
                if doc_name:
                    title_parts.append(doc_name)
                if page is not None:
                    title_parts.append(f"第{page}页")
                title = " ".join(title_parts) if title_parts else "知识库"
                refs.append({
                    "type": "knowledge",
                    "title": title,
                    "source": doc_name or "知识库",
                    "excerpt": excerpt,
                })
        else:
            refs.append({
                "type": "tool",
                "title": name,
                "source": name,
                "excerpt": _j(result)[:240],
            })
    return refs


def _tool_calls_for_history(tool_calls: list[dict]) -> list[dict]:
    normalized = []
    for item in tool_calls:
        fn = item.get("function", item)
        args = fn.get("arguments") or {}
        if not isinstance(args, str):
            args = _j(args)
        normalized.append({
            "id": item.get("id", ""),
            "type": item.get("type", "function"),
            "function": {
                "name": fn.get("name", ""),
                "arguments": args,
            },
        })
    return normalized


async def _yield_final_stream(kwargs: dict, full: list[str], thinking_parts: list[str], timeline: list[dict]):
    logger.info("[DIAG] _yield_final_stream ENTER")
    event_count = 0
    async for event in gateway_router.chat_stream(**kwargs):
        event_count += 1
        event_type = event.get("type")
        content = str(event.get("content") or "")
        logger.info("[DIAG] _yield_final_stream event #%d type=%s content_len=%d", event_count, event_type, len(content))
        if event_type == "thinking" and content:
            thinking_parts.append(content)
            timeline.append({"type": "thinking", "content": content})
            yield f"data: {json.dumps({'type': 'thinking', 'content': content}, ensure_ascii=False)}\n\n".encode("utf-8")
        elif event_type in ("token", "content") and content:
            full.append(content)
            timeline.append({"type": "text", "content": content})
            yield f"data: {json.dumps({'type': 'token', 'content': content}, ensure_ascii=False)}\n\n".encode("utf-8")
        elif event_type == "error" and content:
            yield f"data: {json.dumps({'type': 'error', 'content': content}, ensure_ascii=False)}\n\n".encode("utf-8")
        elif event_type == "done":
            logger.info("[DIAG] _yield_final_stream got done event — stream ending")
    logger.info("[DIAG] _yield_final_stream EXIT after %d events", event_count)


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


# ── 三层提示词管理接口（仅管理员） ─────────────────────────

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


# ── 对话接口 ───────────────────────────────────────────────

@router.get("/conversations")
async def list_conversations(db: AsyncSession = Depends(get_db), user: User = Depends(require_permission("viewer"))):
    items = await conv_svc.list_conversations(db, user.id)
    return ApiResponse(data=[_conversation_payload(item) for item in items])


@router.post("/conversations")
async def create_conversation(payload: CreateConvRequest, db: AsyncSession = Depends(get_db), user: User = Depends(require_permission("viewer"))):
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


# ── 聊天 + 画像进化（3-layer） ─────────────────────────────

@router.post("/chat")
async def chat(payload: ChatRequest, db: AsyncSession = Depends(get_db), user: User = Depends(require_permission("viewer"))):
    # 确保默认数据、画像和表结构迁移存在
    await ensure_timeline_column(db)
    await ensure_default_prompts(db)
    await ensure_user_profile(db, user.id)

    # 持久化用户消息
    await conv_svc.add_message(db, user.id, payload.conversation_id, "user", payload.content)

    # 加载历史 + 用 3 层构建 context
    history = await conv_svc.get_messages(db, user.id, payload.conversation_id)
    messages = await conv_svc.build_context_messages(db, user.id, history)
    tools = tool_discovery.build_tools(user.role)

    async def event_stream():
        logger.info("[DIAG] event_stream ENTER conv=%d user=%d", payload.conversation_id, user.id)
        full: list[str] = []
        thinking_parts: list[str] = []
        tool_events: list[dict] = []
        timeline: list[dict] = []
        try:
            for _round in range(MAX_TOOL_ROUNDS):
                logger.info("[DIAG] event_stream tool_round %d/%d", _round + 1, MAX_TOOL_ROUNDS)
                kwargs: dict = {"messages": messages}
                if payload.profile_key:
                    kwargs["profile_key"] = payload.profile_key
                if tools:
                    kwargs["tools"] = tools
                logger.info("[DIAG] event_stream calling gateway_router.chat")
                result = await gateway_router.chat(**kwargs)
                logger.info("[DIAG] event_stream chat returned tool_calls=%s error=%s",
                    bool(result.get("tool_calls")), bool(result.get("error")))
                if result.get("error"):
                    error_msg = result.get("error") or ""
                    yield f"data: {json.dumps({'type': 'error', 'content': error_msg}, ensure_ascii=False)}\n\n".encode("utf-8")
                    break
                if result.get("thinking"):
                    thinking = str(result["thinking"])
                    thinking_parts.append(thinking)
                    timeline.append({"type": "thinking", "content": thinking})
                    logger.info("[DIAG] timeline APPEND thinking len=%d total=%d", len(thinking), len(timeline))
                    yield f"data: {json.dumps({'type': 'thinking', 'content': thinking}, ensure_ascii=False)}\n\n".encode("utf-8")
                tool_calls = result.get("tool_calls") or []
                if not tool_calls and result.get("finish_reason") == "tool_calls" and tools:
                    result = await recover_tool_calls(messages, payload.profile_key or "deepseek-v4-flash", tools)
                    tool_calls = result.get("tool_calls") or []
                if not tool_calls:
                    logger.info("[DIAG] event_stream entering _yield_final_stream")
                    stream_kwargs: dict = {"messages": messages}
                    if payload.profile_key:
                        stream_kwargs["profile_key"] = payload.profile_key
                    async for chunk in _yield_final_stream(stream_kwargs, full, thinking_parts, timeline):
                        yield chunk
                    logger.info("[DIAG] event_stream _yield_final_stream finished")
                    break
                logger.info("[DIAG] event_stream executing tool_calls count=%d", len(tool_calls))
                messages.append({
                    "role": "assistant",
                    "content": result.get("content") or "",
                    "tool_calls": _tool_calls_for_history(tool_calls),
                })
                for tc in tool_calls:
                    fn = tc.get("function", tc)
                    name = fn.get("name", "")
                    tool_call_id = tc.get("id") or fn.get("id") or ""
                    try:
                        args = fn.get("arguments") or {}
                        if isinstance(args, str):
                            args = json.loads(args)
                    except Exception:
                        args = {}
                    module_key, action = tool_discovery.parse_tool_name(name)
                    call_event = {"type": "tool_call", "name": name, "arguments": args}
                    tool_events.append(call_event)
                    timeline.append(call_event)
                    yield f"data: {_j(call_event)}\n\n".encode("utf-8")
                    try:
                        tool_result = await call_capability(
                            module_key,
                            action,
                            args,
                            caller=f"user:{user.id}",
                            caller_role=user.role,
                        )
                    except Exception as exc:
                        tool_result = {"error": str(exc)}
                    result_event = {"type": "tool_result", "name": name, "result": tool_result}
                    tool_events.append(result_event)
                    timeline.append(result_event)
                    yield f"data: {_j(result_event)}\n\n".encode("utf-8")
                    tool_message = {
                        "role": "tool",
                        "name": name,
                        "content": _j(tool_result),
                    }
                    if tool_call_id:
                        tool_message["tool_call_id"] = tool_call_id
                    messages.append(tool_message)
        except Exception as exc:
            logger.info("[DIAG] event_stream EXCEPTION %s: %s", type(exc).__name__, str(exc)[:300])
            yield f"data: {json.dumps({'type': 'error', 'content': str(exc)}, ensure_ascii=False)}\n\n".encode("utf-8")
        finally:
            # ── 持久化 + 画像进化：用独立 try/except 兜住，失败只记日志，绝不阻断 [DONE] ──
            try:
                from app.database import AsyncSessionLocal
                logger.info("[DIAG] event_stream starting DB persist")
                # tool_events 可能含 datetime 等非 JSON 对象 → 安全序列化一把
                safe_tool_events = json.loads(json.dumps(tool_events, default=str))
                async with AsyncSessionLocal() as s2:
                    if full:
                        msg = await conv_svc.add_message(s2, user.id, payload.conversation_id, "assistant", "".join(full))
                        await conv_svc.add_message_meta(
                            s2,
                            owner_id=user.id,
                            conversation_id=payload.conversation_id,
                            message_id=msg.id,
                            thinking="\n".join(thinking_parts),
                            references=_references_from_tool_events(tool_events),
                            tool_events=safe_tool_events,
                            timeline=timeline,
                        )
                        logger.info("[DIAG] persist DONE msg=%d timeline_len=%d full_len=%d", msg.id, len(timeline), len(full))
                        # 画像进化：fire-and-forget，不阻塞流收尾
                        user_msg_count = await conv_svc.count_conversation_messages(s2, user.id, payload.conversation_id)
                        if user_msg_count > 0 and user_msg_count % EVOLVE_EVERY_N_MESSAGES == 0:
                            logger.info("[DIAG] event_stream submitting profile_evolve task (fire-and-forget)")
                            asyncio.create_task(_submit_profile_evolve_task(payload.conversation_id, user.id))
                            logger.info("[DIAG] event_stream profile_evolve task submitted")
                logger.info("[DIAG] event_stream DB persist done")
            except Exception as exc:
                logger.warning("event_stream persist/evolve failed (non-fatal): %s", exc)
            # ★ 无论正常结束/异常/持久化失败，永远发 [DONE]
            logger.info("[DIAG] event_stream yielding [DONE]")
            yield b"data: [DONE]\n\n"
            logger.info("[DIAG] event_stream EXIT")

    return StreamingResponse(event_stream(), media_type="text/event-stream")


async def _submit_profile_evolve_task(conversation_id: int, owner_id: int) -> None:
    """提交后台画像进化任务到 SystemTaskQueue（fire-and-forget，异常自愈）。"""
    try:
        from datetime import datetime, timezone
        from app.database import AsyncSessionLocal
        from app.models.system import SystemTaskQueue

        async with AsyncSessionLocal() as db:
            # 检查距上次进化是否超过阈值（节流：距上次进化超过 30 分钟才提交）
            from init_db import ensure_user_profile
            profile = await ensure_user_profile(db, owner_id)
            if profile.evolved_at:
                from datetime import timedelta
                if datetime.now(timezone.utc) - profile.evolved_at < timedelta(minutes=30):
                    return
            task = SystemTaskQueue(
                task_type="profile_evolve",
                parameters=json.dumps({"conversation_id": conversation_id, "owner_id": owner_id}),
                status="pending",
                priority=0,
                module="agent",
                creator_id=owner_id,
            )
            db.add(task)
            await db.commit()
    except Exception as exc:
        logger.warning("_submit_profile_evolve_task failed (non-fatal): %s", exc)
