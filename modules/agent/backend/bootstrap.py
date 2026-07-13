"""Agent task and capability bootstrap entry points."""

from __future__ import annotations

import importlib
import logging

from app.services.task_worker import register_task_handler

logger = logging.getLogger("v2.agent").getChild("bootstrap")


def register_agent_tasks() -> None:
    """Register durable Agent task handlers."""
    from .handlers.tasks import (
        _handle_context_compact,
        _handle_knowledge_retrieval_reflect,
        _handle_memory_distill,
        _handle_memory_dream,
        _handle_slow_tool,
    )
    from .services.profile_evolve import handle_profile_evolve

    register_task_handler("profile_evolve", handle_profile_evolve)
    register_task_handler("memory_dream", _handle_memory_dream)
    register_task_handler("memory_distill", _handle_memory_distill)
    register_task_handler("knowledge_retrieval_reflect", _handle_knowledge_retrieval_reflect)
    register_task_handler("agent_execute_slow_tool", _handle_slow_tool)
    register_task_handler("agent_context_compact", _handle_context_compact)
    logger.info("Agent durable task handlers registered")


def register_agent_capabilities() -> None:
    """Load the three authoritative Agent capability registration modules."""
    for module_name in (
        ".handlers.tool",
        ".handlers.tool_guidance",
        ".handlers.workflow",
    ):
        importlib.import_module(module_name, package=__package__)
    logger.info("Agent capability registration modules loaded")


def init_agent_module() -> None:
    register_agent_tasks()
    register_agent_capabilities()
    logger.info("Agent module bootstrapped")
