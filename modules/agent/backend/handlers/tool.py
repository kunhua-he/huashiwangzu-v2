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
    """子 Agent：把子任务委托给一个独立工具循环，拿回结论。

    Supports role-based model routing via ``role`` param (default: "executor").
    Supported roles: executor, planner, reviewer, understanding, retrieval.
    """
    task = params.get("task", "")
    if not task or not isinstance(task, str):
        return {"error": "task is required"}

    caller_role = "viewer"
    extra_tools = params.get("tools") or []
    extra_context = params.get("context") or ""
    agent_role = params.get("role", "executor")

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

        # Resolve profile via role-based template routing
        profile_key = gateway_service.resolve_role_profile(agent_role)
        full_content = ""
        for _round in range(SUBAGENT_MAX_ROUNDS):
            kwargs = {"messages": messages, "tools": tools, "profile_key": profile_key}
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


# ── Capability: agent:skill_manage ──

async def _cap_skill_manage(params: dict, caller: str) -> dict:
    """Manage skills: list, create, update, delete, scan, usage, provenance.

    Review fork proposals CANNOT directly modify skills —
    review-sourced updates go through approval gate (pending_approval).

    Operations:
      - action=list        → list all registered skills
      - action=get         → get a single skill (param: name)
      - action=create      → create a new skill (param: name, description, body, ...)
      - action=update      → update a skill (param: name, updates dict)
      - action=delete      → soft-delete a skill (param: name)
      - action=scan        → scan file skills into registry
      - action=usage       → get usage stats (param: skill_name, days)
      - action=provenance  → get provenance trail (param: skill_name)
      - action=pending-approvals → list pending approvals
    """
    from app.database import AsyncSessionLocal
    from ..services.skill_governance_service import (
        list_skills, get_skill, create_skill, update_skill, delete_skill,
        scan_file_skills_to_registry, get_skill_usage_stats, get_skill_provenance,
        list_pending_skill_approvals, request_skill_approval,
    )

    action = params.get("action", "list")
    caller_uid = _resolve_user_id(caller)

    async with AsyncSessionLocal() as db:
        if action == "list":
            scope = params.get("scope")
            enabled_only = params.get("enabled_only", False)
            skills = await list_skills(db, scope=scope, enabled_only=enabled_only)
            return {"skills": skills, "total": len(skills)}

        elif action == "get":
            name = params.get("name", "")
            if not name:
                return {"error": "name is required"}
            skill = await get_skill(db, name)
            if not skill:
                return {"error": f"Skill '{name}' not found"}
            return {"skill": skill}

        elif action == "create":
            name = params.get("name", "")
            if not name:
                return {"error": "name is required"}
            source = params.get("source", "manual")
            result = await create_skill(
                db,
                name=name,
                description=params.get("description", ""),
                body=params.get("body", ""),
                allowed_tools=params.get("allowed_tools"),
                paths=params.get("paths"),
                scope=params.get("scope", "global"),
                priority=params.get("priority", 0),
                source=source,
                created_by=caller_uid,
            )
            return result

        elif action == "update":
            name = params.get("name", "")
            if not name:
                return {"error": "name is required"}
            updates = params.get("updates", {})
            from_review = params.get("from_review", False)
            result = await update_skill(db, name, updates, updated_by=caller_uid, from_review=from_review)
            return result

        elif action == "delete":
            name = params.get("name", "")
            if not name:
                return {"error": "name is required"}
            result = await delete_skill(db, name, deleted_by=caller_uid)
            return result

        elif action == "scan":
            base_dir = params.get("base_dir", "data/skills")
            result = await scan_file_skills_to_registry(db, base_dir=base_dir, created_by=caller_uid)
            return result

        elif action == "usage":
            skill_name = params.get("skill_name")
            days = params.get("days", 7)
            stats = await get_skill_usage_stats(db, skill_name=skill_name, days=days)
            return {"usage_stats": stats}

        elif action == "provenance":
            skill_name = params.get("skill_name", "")
            if not skill_name:
                return {"error": "skill_name is required"}
            trail = await get_skill_provenance(db, skill_name)
            return {"provenance": trail}

        elif action == "pending-approvals":
            limit = params.get("limit", 50)
            approvals = await list_pending_skill_approvals(db, limit=limit)
            return {"approvals": approvals}

        else:
            return {"error": f"Unknown action: {action}"}