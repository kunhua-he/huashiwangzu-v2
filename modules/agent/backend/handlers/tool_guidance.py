"""Capability handlers for agent tool guidance control plane.

Registered capabilities:
  - agent:list_tool_guides
  - agent:get_tool_guide
  - agent:propose_tool_guide
  - agent:activate_tool_guide
  - agent:disable_tool_guide
  - agent:rollback_tool_guide
  - agent:render_tool_guidance
"""

from __future__ import annotations

import logging

from app.services.file_reader import resolve_caller_user_id
from app.services.module_registry import register_capability

from ..services import tool_guidance_service as tgs

logger = logging.getLogger("v2.agent").getChild("handlers.tool_guidance")

_READ_CONTRACT = {"side_effect_level": "none", "parallel_safe": True}
_WRITE_CONTRACT = {"side_effect_level": "workspace_write", "idempotency": "supported"}
_ADMIN_CONTRACT = {
    "side_effect_level": "admin_config",
    "approval_policy": "requires_confirmation",
    "idempotency": "supported",
}


async def _cap_list_tool_guides(params: dict, caller: str) -> dict:
    """List tool guides with optional filters."""
    from app.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        owner_id = params.get("owner_id")
        if owner_id is None:
            owner_id = resolve_caller_user_id(caller)
        guides = await tgs.list_guides(
            db,
            owner_id=owner_id,
            agent_code=params.get("agent_code"),
            tool_name=params.get("tool_name"),
            scope=params.get("scope"),
            status=params.get("status"),
        )
        return {"guides": guides, "total": len(guides)}


async def _cap_get_tool_guide(params: dict, caller: str) -> dict:
    """Get a single tool guide by id."""
    guide_id = params.get("guide_id")
    if not guide_id:
        return {"error": "guide_id is required"}
    from app.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        guide = await tgs.get_guide(db, int(guide_id))
        if not guide:
            return {"error": f"Tool guide #{guide_id} not found"}
        return {"guide": guide}


async def _cap_propose_tool_guide(params: dict, caller: str) -> dict:
    """Submit a candidate tool guide for review."""
    owner_id = params.get("owner_id")
    if owner_id is None:
        owner_id = resolve_caller_user_id(caller)
    agent_code = params.get("agent_code", "default")
    tool_name = params.get("tool_name", "")
    if not tool_name:
        return {"error": "tool_name is required"}
    from app.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        candidate = await tgs.propose_guide(
            db,
            owner_id=owner_id,
            agent_code=agent_code,
            tool_name=tool_name,
            scope=params.get("scope", "agent"),
            title=params.get("title", ""),
            guide_text=params.get("guide_text", ""),
            failure_policy=params.get("failure_policy"),
            acceptance_policy=params.get("acceptance_policy"),
            source=params.get("source", "manual"),
            proposed_by=resolve_caller_user_id(caller),
            source_trajectory_id=params.get("source_trajectory_id"),
        )
        return {"candidate": candidate}


async def _cap_activate_tool_guide(params: dict, caller: str) -> dict:
    """Activate a tool guide (promote candidate or re-enable)."""
    guide_id = params.get("guide_id")
    if not guide_id:
        return {"error": "guide_id is required"}
    from app.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        guide = await tgs.activate_guide(
            db,
            int(guide_id),
            activated_by=resolve_caller_user_id(caller),
        )
        if not guide:
            return {"error": f"Guide #{guide_id} not found"}
        return {"guide": guide}


async def _cap_disable_tool_guide(params: dict, caller: str) -> dict:
    """Disable a tool guide."""
    guide_id = params.get("guide_id")
    if not guide_id:
        return {"error": "guide_id is required"}
    from app.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        guide = await tgs.disable_guide(
            db,
            int(guide_id),
            disabled_by=resolve_caller_user_id(caller),
        )
        if not guide:
            return {"error": f"Guide #{guide_id} not found"}
        return {"guide": guide}


async def _cap_rollback_tool_guide(params: dict, caller: str) -> dict:
    """Roll back a tool guide to a previous version."""
    guide_id = params.get("guide_id")
    target_version = params.get("version")
    if not guide_id or not target_version:
        return {"error": "guide_id and version are required"}
    from app.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        guide = await tgs.rollback_guide(
            db,
            int(guide_id),
            int(target_version),
            rolled_back_by=resolve_caller_user_id(caller),
        )
        if not guide:
            return {"error": f"Guide #{guide_id} or version {target_version} not found"}
        return {"guide": guide}


async def _cap_render_tool_guidance(params: dict, caller: str) -> dict:
    """Render merged tool guidance for the current runtime context.

    Injects guidance for tools that might be used in the current turn,
    following the merge order: global → enterprise → role → agent → user → session.
    """
    owner_id = resolve_caller_user_id(caller)
    agent_code = params.get("agent_code", "default")
    tool_names = params.get("tool_names", [])
    max_tokens = params.get("max_tokens", 2048)
    from app.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        guidance = await tgs.render_tool_guidance(
            db,
            owner_id=owner_id,
            agent_code=agent_code,
            tool_names=tool_names,
            max_tokens=max_tokens,
        )
        return {"guidance": guidance, "tool_names": tool_names, "length": len(guidance)}


async def _cap_classify_and_degrade(params: dict, caller: str) -> dict:
    """Classify a tool error and return degradation advice."""
    error_class = params.get("error_class", "")
    tool_result = params.get("tool_result", {})
    exception = params.get("exception", "")
    if not error_class and tool_result:
        error_class = tgs.classify_error(tool_result, exception)
    advice = tgs.get_degradation_advice(error_class)
    recipe = tgs.match_degradation_recipe(error_class, params.get("user_input", ""))
    return {
        "error_class": error_class,
        "advice": advice,
        "recipe": recipe,
    }


# ── Register capabilities ──

register_capability(
    "agent", "list_tool_guides", _cap_list_tool_guides,
    description="列出工具指引，可按 owner_id/agent_code/tool_name/scope/status 过滤。",
    brief="列出工具指引",
    parameters={
        "owner_id": {"type": "integer", "description": "所有者 ID，可选"},
        "agent_code": {"type": "string", "description": "Agent 编码过滤"},
        "tool_name": {"type": "string", "description": "工具名过滤"},
        "scope": {"type": "string", "description": "作用域过滤"},
        "status": {"type": "string", "description": "状态过滤"},
    },
    min_role="viewer",
    execution_contract=_READ_CONTRACT,
)
register_capability(
    "agent", "get_tool_guide", _cap_get_tool_guide,
    description="获取单条工具指引详情。",
    brief="查看工具指引",
    parameters={"guide_id": {"type": "integer", "description": "指引 ID"}},
    min_role="viewer",
    execution_contract=_READ_CONTRACT,
)
register_capability(
    "agent", "propose_tool_guide", _cap_propose_tool_guide,
    description="提交候选工具指引。生成 candidate 记录，待 admin 审批后晋升为 active。",
    brief="提交候选工具指引",
    parameters={
        "tool_name": {"type": "string", "description": "工具名"},
        "agent_code": {"type": "string", "description": "Agent 编码"},
        "scope": {"type": "string", "description": "作用域"},
        "title": {"type": "string", "description": "标题"},
        "guide_text": {"type": "string", "description": "指引内容"},
        "failure_policy": {"type": "object", "description": "错误分类与降级策略"},
        "acceptance_policy": {"type": "object", "description": "验收策略"},
    },
    min_role="editor",
    execution_contract=_WRITE_CONTRACT,
)
register_capability(
    "agent", "activate_tool_guide", _cap_activate_tool_guide,
    description="激活工具指引：晋升 candidate 为 active，或重新启用已禁用的指引。",
    brief="激活工具指引",
    parameters={"guide_id": {"type": "integer", "description": "指引或候选 ID"}},
    min_role="admin",
    execution_contract=_ADMIN_CONTRACT,
)
register_capability(
    "agent", "disable_tool_guide", _cap_disable_tool_guide,
    description="禁用工具指引。",
    brief="禁用工具指引",
    parameters={"guide_id": {"type": "integer", "description": "指引 ID"}},
    min_role="admin",
    execution_contract=_ADMIN_CONTRACT,
)
register_capability(
    "agent", "rollback_tool_guide", _cap_rollback_tool_guide,
    description="回滚工具指引到指定版本。",
    brief="回滚工具指引",
    parameters={
        "guide_id": {"type": "integer", "description": "指引 ID"},
        "version": {"type": "integer", "description": "目标版本号"},
    },
    min_role="admin",
    execution_contract=_ADMIN_CONTRACT,
)
register_capability(
    "agent", "render_tool_guidance", _cap_render_tool_guidance,
    description="按合并顺序渲染当前上下文的工具指引。只渲染本轮可能用到的工具。",
    brief="渲染工具指引",
    parameters={
        "agent_code": {"type": "string", "description": "Agent 编码"},
        "tool_names": {"type": "array", "items": {"type": "string"}, "description": "当前可用工具名列表"},
        "max_tokens": {"type": "integer", "description": "最大 token 数"},
    },
    min_role="viewer",
    execution_contract=_READ_CONTRACT,
)
register_capability(
    "agent", "classify_and_degrade", _cap_classify_and_degrade,
    description="分类工具错误并返回降级建议。可根据 tool_result 自动判断错误类型，也可手动指定 error_class。",
    brief="错误分类与降级",
    parameters={
        "error_class": {"type": "string", "description": "已知错误分类（可选，不传则自动判断）"},
        "tool_result": {"type": "object", "description": "工具返回结果含 error/stderr/stdout"},
        "exception": {"type": "string", "description": "异常字符串"},
        "user_input": {"type": "string", "description": "用户输入，用于匹配降级 recipe"},
    },
    min_role="viewer",
    execution_contract=_READ_CONTRACT,
)
