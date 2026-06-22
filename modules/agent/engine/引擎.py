"""引擎编排壳：暴露装配上下文()等给 router，预留压缩接口。"""
import asyncio
import json
import logging
from sqlalchemy.ext.asyncio import AsyncSession
import conversation_service as conv_svc
from 事件存储 import read_events, project_to_messages, record_event
from 预算分配器 import assemble_context, estimate_tokens
from 分层记忆 import 记一笔 as _分层记忆_记一笔, 召回记忆 as _分层记忆_召回记忆, 即时融合 as _分层记忆_即时融合
from 经验记忆 import 匹配经验 as _经验_匹配, 保存经验 as _经验_保存, 经验反馈 as _经验_反馈, 格式化注入段 as _经验_格式化

logger = logging.getLogger("v2.agent.engine.引擎")

# dream 触发节流：每 N 轮对话触发一次
_DREAM_INTERVAL = 5


async def 装配上下文(
    db: AsyncSession,
    conversation_id: int,
    current_user_input: str,
    profile_key: str,
    owner_id: int,
) -> tuple[list[dict], dict]:
    try:
        projected = await project_to_messages(db, conversation_id)
    except Exception as e:
        logger.warning("投影事件失败，回退空投影: %s", e)
        projected = []
    try:
        system_content = await _build_system_content(db, owner_id)
    except Exception as e:
        logger.warning("构建系统提示词失败: %s", e)
        system_content = "You are a helpful AI assistant."
    try:
        messages, diagnosis = assemble_context(projected, system_content, current_user_input, profile_key)
    except Exception as e:
        logger.warning("预算装配失败，回退原始投影+截尾: %s", e)
        messages = [{"role": "system", "content": system_content}]
        messages.extend(projected[-48:] if len(projected) > 48 else projected)
        diagnosis = {"error": str(e), "fallback": "原始投影截尾"}

    # ── 成功经验注入（批3）：语义匹配当前输入，注入 known success path ──
    try:
        matched = await _经验_匹配(current_user_input, limit=2, caller=f"user:{owner_id}")
        injection = _经验_格式化(matched)
        if injection and messages:
            for msg in messages:
                if msg["role"] == "system":
                    msg["content"] += injection
                    break
            diagnosis["experience_injected"] = [e["id"] for e in matched if e.get("id")]
            diagnosis["experience_injection"] = "成功注入" if injection else "无命中"
        else:
            diagnosis["experience_injection"] = "无命中"
    except Exception as e:
        logger.warning("经验注入失败（降级，不阻塞）: %s", e)
        diagnosis["experience_injection"] = f"降级: {e}"

    return messages, diagnosis


async def _build_system_content(db: AsyncSession, owner_id: int) -> str:
    sys_prompt = await conv_svc.get_system_prompt(db)
    ent_prompt = await conv_svc.get_enterprise_prompt(db)
    profile_data = await conv_svc.get_active_user_profile(db, owner_id)
    profile_text = conv_svc._format_profile_text(profile_data)
    layers = []
    if sys_prompt:
        layers.append(sys_prompt)
    if ent_prompt:
        layers.append(ent_prompt)
    if profile_text:
        layers.append(profile_text)
    return "\n\n---\n\n".join(layers)


# ── 已实现接口（批2 事实记忆） ──────────────────────────────

async def 记一笔(db: AsyncSession, conversation_id: int, owner_id: int, messages: list[dict]) -> dict:
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
        # 用分层记忆客户端保存
        result = await _分层记忆_记一笔(
            text=combined[:2000],
            owner_id=owner_id,
            source="auto-distill",
            conversation_id=conversation_id,
        )
        return result
    except Exception as e:
        logger.warning("记一笔 failed (non-fatal): %s", e)
        return {"status": "fallback", "error": str(e)}


async def 压缩(db: AsyncSession, conversation_id: int) -> dict:
    """批3：事件压缩。当前占位，返回空。"""
    logger.info("压缩 [批3预留接口] (conv=%s)", conversation_id)
    return {"status": "placeholder", "note": "【批3实现】"}


async def 召回记忆(db: AsyncSession, owner_id: int, query: str) -> list[dict]:
    """批2：语义召回记忆。调用 memory 模块 recall 能力，含顺链扩展。"""
    try:
        results = await _分层记忆_召回记忆(
            owner_id=owner_id,
            query=query,
            limit=5,
            expand_chain=True,
        )
        return results
    except Exception as e:
        logger.warning("召回记忆 failed (non-fatal): %s", e)
        return []


async def 即时融合注入(owner_id: int, query: str, memory_ids: list[int], budget_remaining: int) -> str | None:
    """如果预算紧（< MEMORY_FUSE_BUDGET_THRESHOLD），用即时融合压缩多条记忆成简报。

    否则返回 None（直接用总结层概要，省一次调用）。
    """
    if not memory_ids:
        return None
    if budget_remaining is not None and budget_remaining < 2000:
        # 预算紧：融合压缩
        return await _分层记忆_即时融合(owner_id, query, memory_ids)
    return None


# 全局 dream 计数器（近似，跨 worker 不精确但够用）
_dream_counter: int = 0


async def 触发定期dream(owner_id: int) -> None:
    """每 DREAM_INTERVAL 次调用触发一次 dream（fire-and-forget）。"""
    global _dream_counter
    _dream_counter += 1
    if _dream_counter % _DREAM_INTERVAL == 0:
        from 分层记忆 import 触发dream
        asyncio.create_task(触发dream(owner_id))


# ── 批3 成功经验：蒸馏 + 结算 ──────────────────────────────

async def 蒸馏经验(
    trigger_condition: str,
    steps: list[dict],
    tools_used: list[str] | None = None,
    source_conversation_id: int | None = None,
    owner_id: int = 0,
) -> None:
    """fire-and-forget：对话成功后，把成功路径蒸馏成一条经验存入经验库。

    降级：失败不影响主对话。
    """
    try:
        steps_str = json.dumps(steps, ensure_ascii=False)
        tools_str = json.dumps(tools_used, ensure_ascii=False) if tools_used else None
        await _经验_保存(
            trigger_condition=trigger_condition,
            steps=steps_str,
            tools_used=tools_str,
            source_conversation_id=source_conversation_id,
            caller=f"user:{owner_id}" if owner_id else "system:engine",
        )
    except Exception as e:
        logger.warning("蒸馏经验 failed (non-fatal): %s", e)


async def 经验结算(
    experience_id: int,
    success: bool,
    note: str | None = None,
    owner_id: int = 0,
) -> None:
    """fire-and-forget：对话结束后，对用过的经验做成功/失败反馈。

    降级：失败不影响主对话。
    """
    try:
        await _经验_反馈(
            experience_id=experience_id,
            success=success,
            note=note,
            caller=f"user:{owner_id}" if owner_id else "system:engine",
        )
    except Exception as e:
        logger.warning("经验结算 failed (non-fatal): %s", e)
