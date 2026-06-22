"""引擎编排壳：暴露装配上下文()等给 router，预留记忆/压缩接口。"""
import logging
from sqlalchemy.ext.asyncio import AsyncSession
import conversation_service as conv_svc
from 事件存储 import read_events, project_to_messages, record_event
from 预算分配器 import assemble_context, estimate_tokens
logger = logging.getLogger("v2.agent.engine.引擎")
PLACEHOLDER_NOTE = "【预留接口：本批未实现，后续批填】"


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


# ── 预留接口（批2/3填） ───────────────────────────────────────

async def 记一笔(db: AsyncSession, conversation_id: int, owner_id: int, messages: list[dict]) -> dict:
    """批2：记忆写入。当前占位，返回空。"""
    logger.info("记一笔 %s (conv=%s)", PLACEHOLDER_NOTE, conversation_id)
    return {"status": "placeholder", "note": PLACEHOLDER_NOTE}


async def 压缩(db: AsyncSession, conversation_id: int) -> dict:
    """批3：事件压缩。当前占位，返回空。"""
    logger.info("压缩 %s (conv=%s)", PLACEHOLDER_NOTE, conversation_id)
    return {"status": "placeholder", "note": PLACEHOLDER_NOTE}


async def 召回记忆(db: AsyncSession, owner_id: int, query: str) -> list[dict]:
    """批2：记忆召回。当前占位，返回空列表。"""
    logger.info("召回记忆 %s (user=%s)", PLACEHOLDER_NOTE, owner_id)
    return []
