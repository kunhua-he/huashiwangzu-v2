"""Agent module bootstrap: single entry point for initialization, task registration,
and capability registration.

Called once at module load time from router.py. Consolidates all side-effect-driven
setup so the router file only owns API routing — not lifecycle management."""

import logging

from app.services.module_registry import register_capability
from app.services.task_worker import register_task_handler

logger = logging.getLogger("v2.agent").getChild("bootstrap")


def register_agent_tasks() -> None:
    """Register all background task handlers."""
    from .services.profile_evolve import handle_profile_evolve
    from .handlers.tasks import _handle_memory_dream, _handle_memory_distill, _handle_slow_tool

    register_task_handler("profile_evolve", handle_profile_evolve)
    register_task_handler("memory_dream", _handle_memory_dream)
    register_task_handler("memory_distill", _handle_memory_distill)
    register_task_handler("agent_execute_slow_tool", _handle_slow_tool)
    logger.info("Agent task handlers registered (profile_evolve, memory_dream, memory_distill, agent_execute_slow_tool)")


def register_agent_capabilities() -> None:
    """Register all cross-module capabilities."""
    from .handlers.tool import (
        _cap_get_system_prompt, _cap_update_system_prompt,
        _cap_get_enterprise_prompt, _cap_update_enterprise_prompt,
        _cap_get_my_profile, _cap_update_my_profile,
        _cap_spawn_subagent,
    )

    from .handlers.tool import _cap_skill_manage

    capabilities = [
        ("agent", "get_system_prompt", _cap_get_system_prompt,
         "读取当前系统提示词（管理员权限）。系统提示词定义了 Agent 的核心行为、知识库使用规则和联网能力规则。",
         "读取系统提示词", {}, "admin"),
        ("agent", "update_system_prompt", _cap_update_system_prompt,
         "更新系统提示词（管理员权限）。当管理员用户要求修改 Agent 底层行为规则时调用此工具。",
         "更新系统提示词", {"content": {"type": "string", "description": "新的系统提示词内容"}}, "admin"),
        ("agent", "get_enterprise_prompt", _cap_get_enterprise_prompt,
         "读取当前企业提示词（管理员权限）。企业提示词包含了公司背景、业务规则等企业上下文信息。",
         "读取企业提示词", {}, "admin"),
        ("agent", "update_enterprise_prompt", _cap_update_enterprise_prompt,
         "更新企业提示词（管理员权限）。当管理员用户要求修改公司/企业背景设定时调用此工具。",
         "更新企业提示词", {"content": {"type": "string", "description": "新的企业提示词内容"}}, "admin"),
        ("agent", "get_my_profile", _cap_get_my_profile,
         "读取当前用户的个人画像。个人画像包含用户的语气偏好、禁忌话题、关注领域和习惯。",
         "读取我的画像", {}, "viewer"),
        ("agent", "update_my_profile", _cap_update_my_profile,
         "更新当前用户的个人画像（仅能改自己的）。owner 固定为当前用户。",
         "更新我的画像", {
             "profile_data": {
                 "type": "object",
                 "description": "画像数据字典",
                 "properties": {
                     "tone": {"type": "string"},
                     "taboos": {"type": "array", "items": {"type": "string"}},
                     "focus": {"type": "array", "items": {"type": "string"}},
                     "habits": {"type": "array", "items": {"type": "string"}},
                 },
             },
         }, "viewer"),
        ("agent", "spawn_subagent", _cap_spawn_subagent,
         "把子任务委托给一个独立子 Agent 执行并拿回结论。",
         "委托子Agent执行任务",
         {"task": {"type": "string"}, "tools": {"type": "array", "items": {"type": "string"}},
          "context": {"type": "string"}}, "viewer"),
        ("agent", "skill_manage", _cap_skill_manage,
         "管理技能：列表、创建、更新、删除、扫描、使用统计和来源追溯。"
         "Review fork 产出的技能 proposal 不能直接修改正式技能，必须走审批（pending_approval）。",
         "管理技能",
         {"action": {"type": "string", "description": "list/get/create/update/delete/scan/usage/provenance/pending-approvals"},
          "name": {"type": "string", "description": "技能名称（create/get/update/delete/provenance 需要）"},
          "description": {"type": "string", "description": "技能描述（create 需要）"},
          "body": {"type": "string", "description": "技能内容（create/update 可选）"},
          "allowed_tools": {"type": "array", "items": {"type": "string"}, "description": "允许的工具列表"},
          "scope": {"type": "string", "description": "作用域 global/project/workspace"},
          "from_review": {"type": "boolean", "description": "是否来自 review fork proposal"}}, "admin"),
    ]

    for module_key, action, handler, desc, brief, params, min_role in capabilities:
        register_capability(
            module_key, action, handler,
            description=desc, brief=brief, parameters=params, min_role=min_role,
        )
    logger.info("Agent capabilities registered (%d)", len(capabilities))


def init_agent_module() -> None:
    """Initialize the agent module at load time."""
    register_agent_tasks()
    register_agent_capabilities()
    logger.info("Agent module bootstrapped")
