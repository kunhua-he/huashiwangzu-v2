"""Cross-module capability registry（带元数据，支持技能发现）。"""
import hashlib
import json
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Awaitable, Callable, Protocol

from app.core.exceptions import ConflictError, NotFound, PermissionDenied
from app.services.semantic_failure import semantic_failure_reason as semantic_failure_reason

logger = logging.getLogger("v2.module_registry")

CapabilityHandler = Callable[[dict, str], Awaitable[dict]]
# key -> {handler, description, parameters, execution_contract, retrieval, ...}
_CAPABILITIES: dict[str, dict] = {}
_PRIVATE_REGISTRATION_OWNER: ContextVar[int | None] = ContextVar(
    "private_registration_owner",
    default=None,
)

# 可信系统主体白名单：caller 以 system: 开头时从此处获取角色
_SERVICE_PRINCIPAL_ROLES = {
    "system:agent-engine": "admin",
    "system:app-loader": "admin",
    "system:content-service": "admin",
    "system:desktop-tools": "admin",
    "system:docs-open": "admin",
    "system:image-vision": "admin",
    "system:task-worker": "admin",
    "system:tool-loop": "admin",
}


def _key(module_key: str, action: str) -> str:
    return f"{module_key}:{action}"


def _current_capability_keys() -> set[str]:
    """Return the current set of all registered capability keys.

    Used by private_module_service to track which capabilities a
    private module registers during activation, so they can be
    properly cleaned up on deactivation.
    """
    return set(_CAPABILITIES.keys())


def _current_capability_snapshot() -> dict[str, dict]:
    """Return a shallow snapshot of capability entries for activation rollback."""
    return {key: dict(value) for key, value in _CAPABILITIES.items()}


def _restore_capability_snapshot(snapshot: dict[str, dict]) -> None:
    """Restore registry state after a failed dynamic module activation."""
    _CAPABILITIES.clear()
    _CAPABILITIES.update({key: dict(value) for key, value in snapshot.items()})


@contextmanager
def private_capability_registration(owner_id: int) -> Iterator[None]:
    """Scope import-time capability registration to a private module owner."""
    token = _PRIVATE_REGISTRATION_OWNER.set(owner_id)
    try:
        yield
    finally:
        _PRIVATE_REGISTRATION_OWNER.reset(token)


def register_capability(
    module_key: str,
    action: str,
    handler: CapabilityHandler,
    description: str = "",
    parameters: dict | None = None,
    min_role: str = "viewer",
    brief: str = "",
    owner_id: int | None = None,
    execution_contract: dict | None = None,
    retrieval: dict | None = None,
) -> None:
    """模块注册一个对外能力。owner_id 非空时标识该能力为私有,仅对应 owner 可调用。"""
    scoped_owner_id = owner_id
    implicit_owner_id = _PRIVATE_REGISTRATION_OWNER.get()
    if scoped_owner_id is None and implicit_owner_id is not None:
        scoped_owner_id = implicit_owner_id

    key = _key(module_key, action)
    existing = _CAPABILITIES.get(key)
    if implicit_owner_id is not None and existing and existing.get("owner_id") != scoped_owner_id:
        raise ConflictError(f"Private capability cannot override existing capability: {key}")

    _CAPABILITIES[key] = {
        "handler": handler,
        "description": description,
        "parameters": parameters or {},
        "min_role": min_role,
        "brief": brief or description[:20],
        "owner_id": scoped_owner_id,
        "execution_contract": _normalize_execution_contract(execution_contract),
        "retrieval": _normalize_retrieval_metadata(retrieval),
    }
    logger.info(
        "Registered capability: %s:%s (scope=%s)",
        module_key, action,
        f"private:owner={scoped_owner_id}" if scoped_owner_id else "public",
    )


def _normalize_execution_contract(value: dict | None) -> dict:
    raw = value if isinstance(value, dict) else {}
    contract_declared = isinstance(value, dict)
    risk_declared = contract_declared and "side_effect_level" in raw
    execution_mode = str(raw.get("execution_mode") or "sync")
    resource_class = str(raw.get("resource_class") or "fast")
    idempotency = str(raw.get("idempotency") or "none")
    side_effect_level = str(raw.get("side_effect_level") or "none")
    approval_default = (
        "requires_confirmation"
        if side_effect_level in {"outbound", "admin", "admin_config", "irreversible"}
        else "none"
    )
    approval_policy = str(raw.get("approval_policy") or approval_default)
    trust_level = str(raw.get("trust_level") or "module_verified")
    return {
        "contract_declared": contract_declared,
        "risk_declared": risk_declared,
        "input_schema": raw.get("input_schema") if isinstance(raw.get("input_schema"), dict) else {},
        "output_schema": raw.get("output_schema") if isinstance(raw.get("output_schema"), dict) else {},
        "execution_mode": execution_mode if execution_mode in {"sync", "async"} else "sync",
        "resource_class": resource_class,
        "timeout_seconds": max(1, int(raw.get("timeout_seconds") or 30)),
        "max_attempts": max(1, min(int(raw.get("max_attempts") or 1), 10)),
        "idempotency": (
            idempotency
            if idempotency in {"required", "supported", "none"}
            else "invalid"
        ),
        "side_effect_level": side_effect_level,
        "approval_policy": approval_policy,
        "trust_level": trust_level,
        "output_reference_types": sorted({str(item) for item in raw.get("output_reference_types", [])}),
        "parallel_safe": bool(raw.get("parallel_safe", False)),
    }


def _normalize_retrieval_metadata(value: dict | None) -> dict:
    raw = value if isinstance(value, dict) else {}
    return {
        "aliases": [str(item).strip() for item in raw.get("aliases", []) if str(item).strip()][:20],
        "when_to_use": str(raw.get("when_to_use") or "").strip(),
        "when_not_to_use": str(raw.get("when_not_to_use") or "").strip(),
        "input_reference_types": sorted({str(item) for item in raw.get("input_reference_types", [])}),
        "expose_to_agent": bool(raw.get("expose_to_agent", True)),
    }


def _capability_contract_hash(capability: dict) -> str:
    payload = {
        "module": capability.get("module"),
        "action": capability.get("action"),
        "parameters": capability.get("parameters") or {},
        "execution_contract": capability.get("execution_contract") or {},
        "retrieval": capability.get("retrieval") or {},
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def unregister_capability(module_key: str, action: str | None = None) -> None:
    """移除模块注册的能力。action 为 None 时移除该模块所有能力。"""
    if action:
        _CAPABILITIES.pop(_key(module_key, action), None)
    else:
        prefix = f"{module_key}:"
        keys_to_remove = [k for k in _CAPABILITIES if k.startswith(prefix)]
        for k in keys_to_remove:
            _CAPABILITIES.pop(k, None)
        logger.info("Unregistered all capabilities for module: %s", module_key)


class AuthenticatedUser(Protocol):
    id: int
    role: str


def _resolve_caller_role(
    caller: str,
    caller_role: str,
    *,
    actor: str | None = None,
    trusted_user_role: bool = False,
) -> str:
    """Resolve effective role from caller identity and caller_role parameter.

    - system:{principal}: role from _SERVICE_PRINCIPAL_ROLES whitelist
    - user:{id}: role must come from a trusted auth context, not module input
    """
    principal = actor or caller
    if principal.startswith("system:"):
        principal_role = _SERVICE_PRINCIPAL_ROLES.get(principal)
        if principal_role is None:
            raise PermissionDenied(
                f"Unknown system principal: {principal}"
            )
        return principal_role
    if caller.startswith("user:"):
        if not trusted_user_role and caller_role != "viewer":
            raise PermissionDenied(
                "user caller role must be resolved by trusted authentication context"
            )
        return caller_role
    raise PermissionDenied(f"Invalid caller format: {caller}")


async def call_capability(
    target_module: str,
    action: str,
    params: dict,
    caller: str,
    caller_role: str = "viewer",
    *,
    actor: str | None = None,
    trusted_user_role: bool = False,
) -> dict:
    """跨模块调用的唯一入口。target 未公开或角色不足则抛异常。

    user:* roles must be supplied through trusted auth helpers. For background
    work on behalf of a user, pass actor=system:* and caller=user:{owner_id};
    the handler receives the caller for data ownership while authorization uses
    the whitelisted system actor.

    如果能力注册了 owner_id，则只有该 owner（user:{owner_id} 或 system: 白名单）可调用。
    """
    entry = _CAPABILITIES.get(_key(target_module, action))
    if not entry:
        raise NotFound(f"Module '{target_module}' does not expose action '{action}'")

    # Owner isolation check: private capabilities are only callable by their owner
    capability_owner = entry.get("owner_id")
    if capability_owner is not None:
        if caller.startswith("user:"):
            caller_id = int(caller.split(":", 1)[1])
            if caller_id != capability_owner:
                raise PermissionDenied(
                    f"Private capability '{target_module}:{action}' is owned by user {capability_owner}"
                )
        elif not caller.startswith("system:"):
            raise PermissionDenied(f"Invalid caller format: {caller}")

    # SQL policy is authoritative for user-scoped calls, including system
    # actors operating on behalf of a user. The model never participates in
    # this decision and cannot restore a capability filtered from its catalog.
    await _authorize_user_capability(
        caller,
        target_module,
        action,
        legacy_min_role=str(entry.get("min_role") or "viewer"),
    )

    resolved_role = _resolve_caller_role(
        caller,
        caller_role,
        actor=actor,
        trusted_user_role=trusted_user_role,
    )
    logger.info(
        "Cross-module call: actor=%s caller=%s role=%s -> %s:%s",
        actor or caller, caller, resolved_role, target_module, action,
    )
    return await entry["handler"](params, caller)


async def call_capability_for_user(
    target_module: str,
    action: str,
    params: dict,
    user: AuthenticatedUser,
) -> dict:
    return await call_capability(
        target_module,
        action,
        params,
        caller=f"user:{user.id}",
        caller_role=user.role,
        trusted_user_role=True,
    )


async def call_capability_as_system(
    target_module: str,
    action: str,
    params: dict,
    *,
    principal: str,
    on_behalf_of_user_id: int | None = None,
) -> dict:
    caller = f"user:{on_behalf_of_user_id}" if on_behalf_of_user_id is not None else principal
    return await call_capability(
        target_module,
        action,
        params,
        caller=caller,
        caller_role="viewer",
        actor=principal,
    )


def _caller_owner_id(caller: str | None) -> int | None:
    if not caller or not caller.startswith("user:"):
        return None
    try:
        return int(caller.split(":", 1)[1])
    except ValueError:
        return None


async def _authorize_user_capability(
    caller: str,
    module_key: str,
    action: str,
    *,
    legacy_min_role: str,
) -> None:
    owner_id = _caller_owner_id(caller)
    if owner_id is None:
        return
    from app.database import AsyncSessionLocal
    from app.services.permission_service import assert_capability_authorized

    async with AsyncSessionLocal() as db:
        await assert_capability_authorized(
            db,
            user_id=owner_id,
            module_key=module_key,
            action=action,
            legacy_min_role=legacy_min_role,
        )
        await db.commit()


def list_capabilities(role: str | None = None, caller: str | None = None) -> list[dict]:
    """List registry metadata without making an authorization decision.

    ``role`` remains as a source-compatible argument for sandbox and contract
    tooling. User-facing callers must use ``authorized_capability_snapshot``;
    textual roles are not a capability authorization boundary.
    """
    caller_owner_id = _caller_owner_id(caller)
    include_all_private = bool(caller and caller.startswith("system:"))
    result = []
    for k, e in _CAPABILITIES.items():
        capability_owner = e.get("owner_id")
        if capability_owner is not None and not include_all_private and capability_owner != caller_owner_id:
            continue
        module_key, action = k.split(":", 1)
        result.append({
            "module": module_key,
            "action": action,
            "description": e["description"],
            "parameters": e["parameters"],
            "min_role": e["min_role"],
            "brief": e.get("brief", e["description"][:20]),
            "execution_contract": e.get("execution_contract", _normalize_execution_contract(None)),
            "retrieval": e.get("retrieval", _normalize_retrieval_metadata(None)),
        })
    return result


def _capabilities_for_owner(caller: str) -> list[dict]:
    caller_owner_id = _caller_owner_id(caller)
    include_all_private = caller.startswith("system:")
    result: list[dict] = []
    for key, entry in _CAPABILITIES.items():
        capability_owner = entry.get("owner_id")
        if capability_owner is not None and not include_all_private and capability_owner != caller_owner_id:
            continue
        module_key, action = key.split(":", 1)
        result.append({
            "module": module_key,
            "action": action,
            "description": entry["description"],
            "parameters": entry["parameters"],
            "brief": entry.get("brief", entry["description"][:20]),
            "execution_contract": entry.get("execution_contract", _normalize_execution_contract(None)),
            "retrieval": entry.get("retrieval", _normalize_retrieval_metadata(None)),
            "legacy_min_role": entry.get("min_role", "viewer"),
        })
    return result


async def authorized_capability_snapshot(*, user_id: int, caller: str | None = None) -> dict:
    """Return a SQL-authorized immutable capability catalog for one user."""
    from app.database import AsyncSessionLocal
    from app.services.permission_service import (
        filter_authorized_capabilities,
        resolve_principal_context,
    )

    resolved_caller = caller or f"user:{int(user_id)}"
    server_candidates = _capabilities_for_owner(resolved_caller)
    async with AsyncSessionLocal() as db:
        principal = await resolve_principal_context(db, int(user_id))
        authorized = await filter_authorized_capabilities(
            db,
            principal=principal,
            capabilities=server_candidates,
        )
        await db.commit()
    authorized = [
        {**item, "contract_hash": _capability_contract_hash(item)}
        for item in authorized
    ]
    authorized.sort(key=lambda item: (int(item["capability_id"]), item["module"], item["action"]))
    canonical = {
        "principal_version": principal.profile_version,
        "capabilities": authorized,
    }
    encoded = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        "catalog_hash": hashlib.sha256(encoded).hexdigest(),
        "principal": principal.to_dict(),
        "capabilities": authorized,
    }


# 内置自检能力（带元数据示例）
async def _echo_capability(params: dict, caller: str) -> dict:
    return {"echo": params, "caller": caller}


register_capability(
    "_self", "echo", _echo_capability,
    description="回显输入参数，用于验证跨模块通路",
    parameters={"任意键值": "原样返回"},
    min_role="viewer",
)
