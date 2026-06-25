"""Tool execution handlers for agent module.

Capability registrations moved to ``bootstrap.py``.
Handlers are imported there and passed to ``register_capability``.

Registered capabilities:
  - agent:get_system_prompt / update_system_prompt
  - agent:get_enterprise_prompt / update_enterprise_prompt
  - agent:get_my_profile / update_my_profile
  - agent:spawn_subagent
"""

from __future__ import annotations

import json
import logging

from app.core.exceptions import PermissionDenied
from app.gateway import service as gateway_service

from ..services import conversation_service as conv_svc
from ..services import tool_discovery
from ..services.model_client import parse_inline_tool_calls, final_clean_content
from .._utils import j as _j

logger = logging.getLogger("v2.agent").getChild("handlers.tool")

SUBAGENT_MAX_ROUNDS = 4
SUBAGENT_CONTEXT_LIMIT = 10


def _resolve_user_id(caller: str) -> int:
    """caller: user:{id} → int user_id。"""
    try:
        prefix, raw_id = caller.split(":", 1)
        if prefix == "user":
            return int(raw_id)
    except (TypeError, ValueError):
        pass
    raise PermissionDenied("Invalid caller")


# ── Capability: agent:get_system_prompt ──

async def _cap_get_system_prompt(params: dict, caller: str) -> dict:
    """读取系统提示词（仅 admin）。"""
    from app.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        content = await conv_svc.get_system_prompt(db)
        return {"content": content}


async def _cap_update_system_prompt(params: dict, caller: str) -> dict:
    """更新系统提示词（仅 admin）。"""
    from app.database import AsyncSessionLocal
    content = params.get("content", "")
    if not content:
        return {"error": "content is required"}
    async with AsyncSessionLocal() as db:
        caller_uid = _resolve_user_id(caller)
        prompt = await conv_svc.update_system_prompt(db, content, caller_uid)
        return {"id": prompt.id, "content": prompt.content, "version": prompt.version}


async def _cap_get_enterprise_prompt(params: dict, caller: str) -> dict:
    """读取企业提示词（仅 admin）。"""
    from app.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        content = await conv_svc.get_enterprise_prompt(db)
        return {"content": content}


async def _cap_update_enterprise_prompt(params: dict, caller: str) -> dict:
    """更新企业提示词（仅 admin）。"""
    from app.database import AsyncSessionLocal
    content = params.get("content", "")
    if not content:
        return {"error": "content is required"}
    async with AsyncSessionLocal() as db:
        caller_uid = _resolve_user_id(caller)
        prompt = await conv_svc.update_enterprise_prompt(db, content, caller_uid)
        return {"id": prompt.id, "content": prompt.content, "version": prompt.version}


async def _cap_get_my_profile(params: dict, caller: str) -> dict:
    """读取自己的个人画像。"""
    from app.database import AsyncSessionLocal
    owner_id = _resolve_user_id(caller)
    async with AsyncSessionLocal() as db:
        from ..init_db import ensure_user_profile
        profile = await ensure_user_profile(db, owner_id)
        return {
            "owner_id": profile.owner_id,
            "profile_data": json.loads(profile.profile_data) if profile.profile_data else {},
            "version": profile.version,
            "evolved_at": profile.evolved_at.isoformat() if profile.evolved_at else None,
            "conversation_count": profile.conversation_count,
        }


async def _cap_update_my_profile(params: dict, caller: str) -> dict:
    """更新自己的个人画像（仅能改自己的，owner 从 caller 解析）。"""
    from app.database import AsyncSessionLocal
    profile_data = params.get("profile_data")
    if not profile_data or not isinstance(profile_data, dict):
        return {"error": "profile_data (dict) is required"}
    owner_id = _resolve_user_id(caller)
    async with AsyncSessionLocal() as db:
        profile = await conv_svc.update_user_profile(db, owner_id, profile_data)
        return {
            "owner_id": profile.owner_id,
            "profile_data": json.loads(profile.profile_data) if profile.profile_data else {},
            "version": profile.version,
        }


# ── Capability: agent:spawn_subagent ──

async def _cap_spawn_subagent(params: dict, caller: str) -> dict:
    """子 Agent：把子任务委托给一个独立工具循环，拿回结论。"""
    task = params.get("task", "")
    if not task or not isinstance(task, str):
        return {"error": "task is required"}

    caller_role = "viewer"
    extra_tools = params.get("tools") or []
    extra_context = params.get("context") or ""

    try:
        system_prompt = (
            "你是一个子 Agent，专注于完成一项具体任务，然后返回结论。\n\n"
            f"任务：{task}\n\n"
        )
        if extra_context:
            system_prompt += f"参考上下文：\n{extra_context}\n\n"
        system_prompt += (
            "规则：\n"
            "1. 使用可用工具完成任务，不要闲聊。\n"
            f"2. 最多 {SUBAGENT_MAX_ROUNDS} 轮工具调用，超限则返回已有结论。\n"
            "3. 完成目标后，清晰总结结论。\n"
            "4. 如果工具调用失败，尝试替代方案。\n"
            "5. 用中文回答。"
        )

        tools = tool_discovery.build_tools(caller_role)
        if extra_tools:
            allowed = set(extra_tools) | {"skill_list", "skill_describe", "skill_use"}
            tools = [t for t in tools if t.get("function", {}).get("name", "") in allowed]

        messages = [{"role": "system", "content": system_prompt}]

        full_content = ""
        for _round in range(SUBAGENT_MAX_ROUNDS):
            kwargs = {"messages": messages, "tools": tools}
            result = await gateway_service.chat(**kwargs)

            if result.get("error"):
                full_content = f"子 Agent 执行出错：{result['error']}"
                break

            content = result.get("content", "")
            tool_calls = result.get("tool_calls") or []

            if not tool_calls:
                clean_content, inline_calls = parse_inline_tool_calls(content)
                if inline_calls:
                    result["content"] = clean_content
                    tool_calls = inline_calls

            if not tool_calls:
                full_content = content
                break

            from .._utils import tool_calls_for_history
            messages.append({
                "role": "assistant",
                "content": content,
                "tool_calls": tool_calls_for_history(tool_calls),
            })

            for tc in tool_calls:
                fn = tc.get("function", tc)
                name = fn.get("name", "")
                try:
                    args = fn.get("arguments") or {}
                    if isinstance(args, str):
                        args = json.loads(args)
                except Exception:
                    args = {}

                if name == "skill_list":
                    tool_result = await tool_discovery.handle_skill_list(args, caller_role)
                elif name == "skill_describe":
                    tool_result = await tool_discovery.handle_skill_describe(args, caller_role)
                elif name == "skill_use":
                    tool_result = await tool_discovery.handle_skill_use(args, caller=caller, caller_role=caller_role)
                else:
                    from app.services.module_registry import call_capability
                    module_key, action = tool_discovery.parse_tool_name(name)
                    tool_result = await call_capability(
                        module_key, action, args, caller=caller, caller_role=caller_role,
                    )

                messages.append({
                    "role": "tool",
                    "name": name,
                    "content": _j(tool_result),
                    "tool_call_id": tc.get("id", ""),
                })

        if not full_content:
            for msg in reversed(messages):
                if msg["role"] == "assistant":
                    full_content = msg.get("content", "") or ""
                    break

        full_content = final_clean_content(full_content)

        return {
            "success": True,
            "data": {
                "conclusion": full_content or "子 Agent 未生成结论",
                "rounds_used": _round + 1,
                "messages_count": len(messages),
            },
        }
    except Exception as exc:
        return {"error": f"子 Agent 执行异常：{exc}"}



