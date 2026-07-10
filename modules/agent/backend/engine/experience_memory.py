"""engine与 memory 模块之间的成功经验薄客户端。
走框架跨模块通路，不直读 memory 表。"""
import json
import logging

from app.services.module_registry import call_capability_as_system

logger = logging.getLogger("v2.agent").getChild("engine.experience_memory")

EXPERIENCE_INJECTION_TEMPLATE = (
    "\n\n💡已知成功路径：当前请求与以下成功经验相似——"
    "\n触发：{trigger}"
    "\n路径：{steps_short}"
    "\n（参考但需结合当前情况验证，不足则正常摸索）"
)


async def save_experience(
    trigger_condition: str,
    steps: str,
    tools_used: str | None = None,
    source_conversation_id: int | None = None,
    caller: str = "system:agent-engine",
) -> dict:
    """保存一条成功经验到 memory 模块。走框架跨模块通路。"""
    try:
        owner_id = _owner_id_from_caller(caller)
        result = await call_capability_as_system(
            "memory", "save_experience",
            {
                "trigger_condition": trigger_condition,
                "steps": steps,
                "tools_used": tools_used,
                "source_conversation_id": source_conversation_id,
            },
            principal="system:agent-engine",
            on_behalf_of_user_id=owner_id,
        )
        return result
    except Exception as e:
        logger.warning("保存经验 failed (non-fatal): %s", e)
        return {"success": False, "error": str(e), "fallback": True}


async def match_experience(
    query: str,
    limit: int = 2,
    caller: str = "system:agent-engine",
) -> list[dict]:
    """语义匹配当前输入相关的成功经验。失败返回空列表。"""
    if not query or not query.strip():
        return []
    try:
        owner_id = _owner_id_from_caller(caller)
        result = await call_capability_as_system(
            "memory", "match_experience",
            {"query": query, "limit": limit},
            principal="system:agent-engine",
            on_behalf_of_user_id=owner_id,
        )
        if result and result.get("success") and result.get("data"):
            return result["data"]
        return []
    except Exception as e:
        logger.warning("匹配经验 failed (non-fatal): %s", e)
        return []


async def experience_feedback(
    experience_id: int,
    success: bool,
    note: str | None = None,
    caller: str = "system:agent-engine",
) -> dict:
    """反馈经验执行结果：成功加权 / 失败降权+注释。"""
    try:
        owner_id = _owner_id_from_caller(caller)
        result = await call_capability_as_system(
            "memory", "experience_feedback",
            {
                "experience_id": experience_id,
                "success": success,
                "note": note,
            },
            principal="system:agent-engine",
            on_behalf_of_user_id=owner_id,
        )
        return result
    except Exception as e:
        logger.warning("经验反馈 failed (non-fatal): %s", e)
        return {"success": False, "error": str(e), "fallback": True}


def _owner_id_from_caller(caller: str) -> int | None:
    if not caller.startswith("user:"):
        return None
    try:
        return int(caller.split(":", 1)[1])
    except ValueError:
        return None


def format_injection(experiences: list[dict]) -> str | None:
    """将匹配到的经验格式化为提示注入段。无可注入内容时返回 None。"""
    if not experiences:
        return None
    segments = []
    for exp in experiences[:2]:
        trigger = exp.get("trigger_condition", "")
        steps_raw = exp.get("steps", "[]")
        try:
            steps_list = json.loads(steps_raw) if isinstance(steps_raw, str) else steps_raw
        except (json.JSONDecodeError, TypeError):
            steps_list = []
        steps_short = "; ".join(
            f"{s.get('tool_name', s.get('意图', '?'))}" for s in (steps_list or [])[:4]
        ) if steps_list else steps_raw[:120]
        net_weight = exp.get("net_weight", exp.get("success_weight", 1) or 1)
        segments.append(
            f"· 经验（权重{net_weight}）：{trigger[:100]}"
            f"\n  路径：{steps_short[:200]}"
        )
    if not segments:
        return None
    return "\n\n---\n\n💡本轮已命中成功经验（优先证据）：\n" + "\n".join(segments) + (
        "\n使用规则：若经验与当前问题不冲突，应优先沿用，避免重复探索；"
        "若不适用，先说明冲突原因，再选择新的证据路径。"
    )
