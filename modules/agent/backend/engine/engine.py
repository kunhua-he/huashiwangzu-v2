"""engine编排壳：暴露装配上下文()等给 router。批4：compressor、fallback_chain接入。批5：工具编排、三层记忆、快照、skills注入。"""
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from .compressor import compress_middle_with_snapshot as _compress_with_snapshot
from .compressor import hard_truncate_tail as _hard_truncate_tail
from .event_store import read_events
from .fallback_chain import chat_stream_with_fallback as _chat_stream_with_fallback
from .fallback_chain import chat_with_fallback as _chat_with_fallback
from .layered_memory import fuse as _layered_memory_fuse
from .layered_memory import recall as _layered_memory_recall
from .layered_memory import record as _layered_memory_record

logger = logging.getLogger("v2.agent").getChild("engine.engine")

# dream 触发节流：每 N 轮对话触发一次
_DREAM_INTERVAL = 5
_COMPRESSION_TOKEN_HEADROOM = 5000


async def assemble_context(
    db: AsyncSession,
    conversation_id: int,
    current_user_input: str,
    profile_key: str,
    owner_id: int,
    agent_code: str = "erp_chat",
) -> tuple[list[dict], dict]:
    """Context assembly pipeline. Delegates to context_pipeline.run_pipeline().

    Each stage is independently testable. See context_pipeline.py for stage details.
    """
    from .context_pipeline import run_pipeline
    return await run_pipeline(db, conversation_id, current_user_input, profile_key, owner_id, agent_code)


# ── 批5：模块级单例 ──────────────────────────────────────────────

# ── 已实现接口（批2 事实记忆） ──────────────────────────────

async def record_turn(db: AsyncSession, conversation_id: int, owner_id: int, messages: list[dict]) -> dict:
    """批2：从对话消息中提取事实记忆并保存。调用 memory 模块 save 能力。"""
    try:
        # 从对话中提取关键事实（仅 user 和 assistant 消息）
        memory_texts = []
        for msg in messages[-6:]:  # 只看最近几轮
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role in ("user", "assistant") and isinstance(content, str) and len(content) > 20:
                memory_texts.append(f"[{role}] {content[:500]}")
        if not memory_texts:
            return {"status": "skipped", "note": "无可提取的记忆内容"}

        combined = "\n\n".join(memory_texts)
        # 用layered_memory客户端保存
        result = await _layered_memory_record(
            text=combined[:2000],
            owner_id=owner_id,
            source="auto-distill",
            conversation_id=conversation_id,
        )
        return result
    except Exception as e:
        logger.warning("记一笔 failed (non-fatal): %s", e)
        return {"status": "fallback", "error": str(e)}


async def compress(db: AsyncSession, conversation_id: int, profile_key: str = "gemma-4") -> dict:
    """批4：事件压缩。调compressor插入 compaction 事件，不删原始事件。"""
    logger.info("压缩 (conv=%s)", conversation_id)
    try:
        all_events = await read_events(db, conversation_id)
        if len(all_events) <= 30:
            return {"status": "skipped", "reason": "事件数不足"}
        result = await _compress_with_snapshot(db, conversation_id, all_events, profile_key=profile_key)
        return result
    except Exception as e:
        logger.warning("compress失败: %s", e)
        try:
            all_events = await read_events(db, conversation_id)
            return await _hard_truncate_tail(db, conversation_id, all_events)
        except Exception as e2:
            return {"status": "error", "error": str(e2)}


async def recall_memory(db: AsyncSession, owner_id: int, query: str) -> list[dict]:
    """批2：语义召回记忆。调用 memory 模块 recall 能力，含顺链扩展。"""
    try:
        results = await _layered_memory_recall(
            owner_id=owner_id,
            query=query,
            limit=5,
            expand_chain=True,
        )
        return results
    except Exception as e:
        logger.warning("召回记忆 failed (non-fatal): %s", e)
        return []


async def fuse_inject(owner_id: int, query: str, memory_ids: list[int], budget_remaining: int) -> str | None:
    """如果预算紧（< MEMORY_FUSE_BUDGET_THRESHOLD），用即时融合压缩多条记忆成简报。

    否则返回 None（直接用总结层概要，省一次调用）。
    """
    if not memory_ids:
        return None
    if budget_remaining is not None and budget_remaining < 2000:
        # 预算紧：融合压缩
        return await _layered_memory_fuse(owner_id, query, memory_ids)
    return None


# 全局 dream 计数器（近似，跨 worker 不精确但够用）
_dream_counter: int = 0


async def trigger_dream(owner_id: int) -> None:
    """每 DREAM_INTERVAL 次调用触发一次 dream（通过 SystemTaskQueue）。"""
    global _dream_counter
    _dream_counter += 1
    if _dream_counter % _DREAM_INTERVAL == 0:
        try:
            from app.database import AsyncSessionLocal
            from app.services.task_dispatcher import publish_task

            async with AsyncSessionLocal() as db:
                await publish_task(
                    db,
                    task_type="memory_dream",
                    module="agent",
                    owner_id=owner_id,
                    body={"owner_id": owner_id},
                    requested_by=f"user:{owner_id}",
                    trigger="agent.memory_dream",
                    priority=0,
                )
                await db.commit()
        except Exception as e:
            logger.warning("dream enqueue failed (non-fatal): %s", e)


# ── 模型调用兼容壳：fallback 由 gateway 统一裁决 ───────────────────────

async def chat_with_degradation_chain(
    messages: list[dict],
    profile_key: str,
    tools: list[dict] | None = None,
    conversation_id: int | None = None,
    response_format: dict | None = None,
) -> dict:
    """Call the framework gateway once; gateway owns model fallback."""
    try:
        return await _chat_with_fallback(
            messages,
            profile_key,
            tools,
            conversation_id=conversation_id,
            response_format=response_format,
        )
    except Exception as e:
        logger.error("gateway chat failed: %s", e)
        return {"error": str(e), "content": f"(模型调用失败：{e})"}


async def chat_stream_with_degradation_chain(
    messages: list[dict],
    profile_key: str,
    tools: list[dict] | None = None,
    conversation_id: int | None = None,
    response_format: dict | None = None,
):
    """Stream gateway events directly; gateway owns model fallback."""
    try:
        async for event in _chat_stream_with_fallback(
            messages,
            profile_key,
            tools,
            conversation_id=conversation_id,
            response_format=response_format,
        ):
            yield event
    except Exception as e:
        logger.error("gateway stream chat failed: %s", e)
        yield {"type": "error", "content": f"(流式模型调用失败：{e})"}
