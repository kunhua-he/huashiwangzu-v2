"""Cross-module capability registry.

The single authoritative channel for module-to-module calls. A module registers
the capabilities it exposes; callers invoke them through here. Framework validates
(only registered = public) and audits. Same pattern as task_worker handlers.
"""
import logging
from typing import Awaitable, Callable

from app.core.exceptions import NotFound

logger = logging.getLogger("v2.module_registry")

# handler(params: dict, caller: str) -> dict
CapabilityHandler = Callable[[dict, str], Awaitable[dict]]
_CAPABILITIES: dict[str, CapabilityHandler] = {}


def _key(module_key: str, action: str) -> str:
    return f"{module_key}:{action}"


def register_capability(module_key: str, action: str, handler: CapabilityHandler) -> None:
    """模块调用此函数，声明并注册一个对外开放的能力。注册即公开，未注册的不可被调用。"""
    _CAPABILITIES[_key(module_key, action)] = handler
    logger.info("Registered capability: %s:%s", module_key, action)


async def call_capability(target_module: str, action: str, params: dict, caller: str) -> dict:
    """跨模块调用的唯一入口。target 未公开该能力则抛 NotFound。"""
    handler = _CAPABILITIES.get(_key(target_module, action))
    if not handler:
        raise NotFound(f"Module '{target_module}' does not expose action '{action}'")
    logger.info("Cross-module call: caller=%s -> %s:%s", caller, target_module, action)
    return await handler(params, caller)


def list_capabilities() -> list[str]:
    return sorted(_CAPABILITIES.keys())


# 内置自检能力，用于验证链路（调用方传什么原样回显）
async def _echo_capability(params: dict, caller: str) -> dict:
    return {"echo": params, "caller": caller}


register_capability("_self", "echo", _echo_capability)
