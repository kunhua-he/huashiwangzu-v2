"""Task handler registry and executor compatibility helpers.

Scheduling deliberately does not live here.  ``task_dispatcher`` is the sole
component allowed to claim, lease, retry or supervise queue rows.  Modules keep
using this small registry so their task registrations stay source-compatible.
"""
from __future__ import annotations

import logging
from typing import Awaitable, Callable

from app.models.system import SystemTaskQueue
from app.services.semantic_failure import semantic_failure_reason

logger = logging.getLogger("v2.task_handlers")

TaskHandler = Callable[[dict], Awaitable[dict | None]]
_HANDLERS: dict[str, TaskHandler] = {}


def register_task_handler(task_type: str, handler: TaskHandler) -> None:
    """Register one module handler; scheduling metadata is owned by Dispatcher."""
    from app.services.task_dispatcher import ensure_task_definition

    if not task_type:
        raise ValueError("task_type is required")
    _HANDLERS[task_type] = handler
    ensure_task_definition(task_type)
    logger.info("Registered task handler: %s", task_type)


def has_task_handler(task_type: str) -> bool:
    return task_type in _HANDLERS


async def _echo_handler(parameters: dict) -> dict:
    return {"echo": parameters}


_HANDLERS["_echo"] = _echo_handler


def _result_is_semantic_failure(result: object) -> tuple[bool, str | None]:
    reason = semantic_failure_reason(result)
    return reason is not None, reason


async def _run_handler(task: SystemTaskQueue) -> tuple[bool, dict | None, str | None]:
    """Run a registered handler with the fixed-envelope body plus DB metadata."""
    handler = _HANDLERS.get(task.task_type)
    if handler is None:
        return False, None, f"No handler registered for task_type '{task.task_type}'"
    try:
        from app.services.task_dispatcher import unpack_task_parameters

        params = unpack_task_parameters(task.parameters)
    except ValueError as exc:
        return False, None, str(exc)
    params["task_id"] = int(task.id)
    if task.document_id is not None:
        params["document_id"] = int(task.document_id)
    if task.stage_key:
        params["stage"] = str(task.stage_key)
    if task.lane_key:
        params["lane"] = str(task.lane_key)
    if task.dependency_key:
        params["dependency_key"] = str(task.dependency_key)
    try:
        result = await handler(params)
        failed, error = _result_is_semantic_failure(result)
        return (False, result, error) if failed else (True, result, None)
    except Exception as exc:
        logger.exception("Task %s (%s) handler failed", task.id, task.task_type)
        return False, None, str(exc)
