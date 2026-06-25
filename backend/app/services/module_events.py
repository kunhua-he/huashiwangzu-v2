"""Lightweight in-process event system for cross-module decoupling.

Replaces hardcoded call_capability in framework code with event emission.
Module handlers register interest in events; framework code emits events
without knowing which modules (if any) will handle them.

Governance metadata shared with module_registry:
  - module_key / description / contract_version / timeout / trace
"""

import logging
import uuid
from typing import Awaitable, Callable
from datetime import datetime, timezone

logger = logging.getLogger("v2.module_events")

EventHandler = Callable[[dict, str, str], Awaitable[dict]]

_event_handlers: dict[str, list[dict]] = {}
"""event_name -> [{module_key, handler, description, contract_version}]"""


def register_module_event_handler(
    event_name: str,
    handler: EventHandler,
    module_key: str,
    description: str = "",
    contract_version: str = "1.0.0",
) -> None:
    """Module registers itself to receive event_name events.

    Governance fields:
      - description: 事件处理器的用途说明
      - contract_version: 事件契约版本号
    """
    if event_name not in _event_handlers:
        _event_handlers[event_name] = []
    existing = [e for e in _event_handlers[event_name] if e["module_key"] == module_key]
    if existing:
        existing[0]["handler"] = handler
        existing[0]["description"] = description
        existing[0]["contract_version"] = contract_version
    else:
        _event_handlers[event_name].append({
            "module_key": module_key,
            "handler": handler,
            "description": description,
            "contract_version": contract_version,
        })
    logger.info("Registered event handler: %s <- %s (contract=%s)", event_name, module_key, contract_version)


async def emit_module_event(
    event_name: str,
    payload: dict,
    caller: str,
    caller_role: str = "viewer",
    trace_id: str | None = None,
) -> list[dict]:
    """Emit an event. Each registered handler is called sequentially.

    trace_id: 调用方传入的追踪 ID，与 call_capability 的 trace 共用同一共识。
    Returns per-handler results with trace metadata.
    """
    trace_id = trace_id or str(uuid.uuid4())
    handlers = _event_handlers.get(event_name, [])
    if not handlers:
        logger.debug("No handlers registered for event '%s'", event_name)
        return []

    results: list[dict] = []
    for entry in handlers:
        try:
            handler_result = await entry["handler"](payload, caller, caller_role)
            results.append({
                "module_key": entry["module_key"],
                "success": True,
                "result": handler_result,
                "_trace": {
                    "trace_id": trace_id,
                    "event": event_name,
                    "contract_version": entry.get("contract_version", "1.0.0"),
                    "ts": datetime.now(timezone.utc).isoformat(),
                },
            })
        except Exception as exc:
            logger.warning(
                "Event '%s' handler for module '%s' failed: %s",
                event_name, entry["module_key"], exc,
            )
            results.append({
                "module_key": entry["module_key"],
                "success": False,
                "error": str(exc),
                "_trace": {
                    "trace_id": trace_id,
                    "event": event_name,
                    "contract_version": entry.get("contract_version", "1.0.0"),
                    "ts": datetime.now(timezone.utc).isoformat(),
                },
            })
    return results
