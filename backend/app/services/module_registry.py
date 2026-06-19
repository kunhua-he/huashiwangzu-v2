"""Cross-module capability registry（带元数据，支持技能发现）。"""
import logging
from typing import Awaitable, Callable

from app.core.exceptions import NotFound

logger = logging.getLogger("v2.module_registry")

CapabilityHandler = Callable[[dict, str], Awaitable[dict]]
# key -> {handler, description, parameters, min_role}
_CAPABILITIES: dict[str, dict] = {}

_ROLE_ORDER = {"viewer": 0, "editor": 1, "admin": 2}


def _key(module_key: str, action: str) -> str:
    return f"{module_key}:{action}"


def register_capability(
    module_key: str,
    action: str,
    handler: CapabilityHandler,
    description: str = "",
    parameters: dict | None = None,
    min_role: str = "viewer",
) -> None:
    """模块注册一个对外能力。description/parameters/min_role 供技能发现用。"""
    _CAPABILITIES[_key(module_key, action)] = {
        "handler": handler,
        "description": description,
        "parameters": parameters or {},
        "min_role": min_role,
    }
    logger.info("Registered capability: %s:%s", module_key, action)


async def call_capability(target_module: str, action: str, params: dict, caller: str) -> dict:
    """跨模块调用的唯一入口。target 未公开该能力则抛 NotFound。"""
    entry = _CAPABILITIES.get(_key(target_module, action))
    if not entry:
        raise NotFound(f"Module '{target_module}' does not expose action '{action}'")
    logger.info("Cross-module call: caller=%s -> %s:%s", caller, target_module, action)
    return await entry["handler"](params, caller)


def list_capabilities(role: str | None = None) -> list[dict]:
    """列出能力元数据（不含 handler）。传 role 则按权限过滤（只返回该角色可调的）。"""
    result = []
    for k, e in _CAPABILITIES.items():
        if role and _ROLE_ORDER.get(role, 0) < _ROLE_ORDER.get(e["min_role"], 0):
            continue
        module_key, action = k.split(":", 1)
        result.append({
            "module": module_key,
            "action": action,
            "description": e["description"],
            "parameters": e["parameters"],
            "min_role": e["min_role"],
        })
    return result


# 内置自检能力（带元数据示例）
async def _echo_capability(params: dict, caller: str) -> dict:
    return {"echo": params, "caller": caller}


register_capability(
    "_self", "echo", _echo_capability,
    description="回显输入参数，用于验证跨模块通路",
    parameters={"任意键值": "原样返回"},
    min_role="viewer",
)
