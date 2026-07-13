from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Iterable

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import PermissionDenied
from app.models.permission import (
    CapabilityIdentity,
    CapabilityPermissionRequirement,
    PermissionDefinition,
    PermissionSet,
    PermissionSetMember,
    UserPermissionGrant,
    UserPermissionSetGrant,
)
from app.models.user import User

_LEGACY_PERMISSION_KEYS = {
    "editor": ("capability.legacy.editor", "能力编辑权限"),
    "admin": ("capability.legacy.admin", "能力管理权限"),
}
_LEGACY_SET_KEYS = {
    "editor": ("legacy.role.editor", "兼容编辑权限组"),
    "admin": ("legacy.role.admin", "兼容管理权限组"),
}


@dataclass(frozen=True)
class PrincipalContext:
    user_id: int
    permission_ids: tuple[int, ...]
    organization_id: int | None = None
    department_ids: tuple[int, ...] = ()
    position_ids: tuple[int, ...] = ()
    profile_version: str = ""

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "permission_ids": list(self.permission_ids),
            "organization_id": self.organization_id,
            "department_ids": list(self.department_ids),
            "position_ids": list(self.position_ids),
            "profile_version": self.profile_version,
        }


def _principal_version(payload: dict) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:20]


async def resolve_principal_context(db: AsyncSession, user_id: int) -> PrincipalContext:
    await _sync_legacy_role_grants(db, int(user_id))
    direct = select(UserPermissionGrant.permission_id).join(
        PermissionDefinition,
        PermissionDefinition.id == UserPermissionGrant.permission_id,
    ).where(
        UserPermissionGrant.user_id == user_id,
        PermissionDefinition.enabled.is_(True),
    )
    inherited = (
        select(PermissionSetMember.permission_id)
        .join(
            UserPermissionSetGrant,
            UserPermissionSetGrant.permission_set_id == PermissionSetMember.permission_set_id,
        )
        .join(PermissionSet, PermissionSet.id == PermissionSetMember.permission_set_id)
        .join(PermissionDefinition, PermissionDefinition.id == PermissionSetMember.permission_id)
        .where(
            UserPermissionSetGrant.user_id == user_id,
            PermissionSet.enabled.is_(True),
            PermissionDefinition.enabled.is_(True),
        )
    )
    direct_ids = {int(value) for value in (await db.execute(direct)).scalars().all()}
    inherited_ids = {int(value) for value in (await db.execute(inherited)).scalars().all()}
    permission_ids = tuple(sorted(direct_ids | inherited_ids))
    version_payload = {
        "user_id": int(user_id),
        "permission_ids": permission_ids,
        "organization_id": None,
        "department_ids": (),
        "position_ids": (),
    }
    return PrincipalContext(
        user_id=int(user_id),
        permission_ids=permission_ids,
        profile_version=_principal_version(version_payload),
    )


async def _legacy_permission_ids(db: AsyncSession) -> dict[str, int]:
    for role, (stable_key, display_name) in _LEGACY_PERMISSION_KEYS.items():
        await db.execute(
            insert(PermissionDefinition)
            .values(
                stable_key=stable_key,
                display_name=display_name,
                scope="capability",
                enabled=True,
            )
            .on_conflict_do_nothing(index_elements=["stable_key"])
        )
    rows = (
        await db.execute(
            select(PermissionDefinition).where(
                PermissionDefinition.stable_key.in_(
                    {value[0] for value in _LEGACY_PERMISSION_KEYS.values()}
                )
            )
        )
    ).scalars().all()
    by_key = {row.stable_key: int(row.id) for row in rows}
    return {
        role: by_key[stable_key]
        for role, (stable_key, _display_name) in _LEGACY_PERMISSION_KEYS.items()
    }


async def _sync_legacy_role_grants(db: AsyncSession, user_id: int) -> None:
    role = (await db.execute(select(User.role).where(User.id == user_id))).scalar_one_or_none()
    if role is None:
        return
    permission_ids = await _legacy_permission_ids(db)
    for role_name, (stable_key, display_name) in _LEGACY_SET_KEYS.items():
        await db.execute(
            insert(PermissionSet)
            .values(
                stable_key=stable_key,
                display_name=display_name,
                system_managed=True,
                enabled=True,
            )
            .on_conflict_do_nothing(index_elements=["stable_key"])
        )
    sets = (
        await db.execute(
            select(PermissionSet).where(
                PermissionSet.stable_key.in_({value[0] for value in _LEGACY_SET_KEYS.values()})
            )
        )
    ).scalars().all()
    set_by_key = {row.stable_key: int(row.id) for row in sets}
    editor_set_id = set_by_key[_LEGACY_SET_KEYS["editor"][0]]
    admin_set_id = set_by_key[_LEGACY_SET_KEYS["admin"][0]]
    memberships = {
        editor_set_id: {permission_ids["editor"]},
        admin_set_id: {permission_ids["editor"], permission_ids["admin"]},
    }
    for permission_set_id, member_ids in memberships.items():
        for permission_id in member_ids:
            await db.execute(
                insert(PermissionSetMember)
                .values(permission_set_id=permission_set_id, permission_id=permission_id)
                .on_conflict_do_nothing(index_elements=["permission_set_id", "permission_id"])
            )
    desired_set_id = {
        "viewer": None,
        "editor": editor_set_id,
        "admin": admin_set_id,
    }.get(str(role))
    legacy_set_ids = {editor_set_id, admin_set_id}
    await db.execute(
        delete(UserPermissionSetGrant).where(
            UserPermissionSetGrant.user_id == user_id,
            UserPermissionSetGrant.permission_set_id.in_(legacy_set_ids),
        )
    )
    if desired_set_id is not None:
        await db.execute(
            insert(UserPermissionSetGrant)
            .values(user_id=user_id, permission_set_id=desired_set_id)
            .on_conflict_do_nothing(index_elements=["user_id", "permission_set_id"])
        )


async def _sync_legacy_capability_requirements(
    db: AsyncSession,
    *,
    capabilities: list[dict],
    identity_map: dict[tuple[str, str], int],
) -> None:
    permission_ids = await _legacy_permission_ids(db)
    legacy_permission_ids = set(permission_ids.values())
    capability_ids = set(identity_map.values())
    if capability_ids:
        await db.execute(
            delete(CapabilityPermissionRequirement).where(
                CapabilityPermissionRequirement.capability_id.in_(capability_ids),
                CapabilityPermissionRequirement.permission_id.in_(legacy_permission_ids),
            )
        )
    for item in capabilities:
        required_role = str(item.get("legacy_min_role") or "viewer")
        permission_id = permission_ids.get(required_role)
        capability_id = identity_map.get((str(item["module"]), str(item["action"])))
        if permission_id is None or capability_id is None:
            continue
        await db.execute(
            insert(CapabilityPermissionRequirement)
            .values(capability_id=capability_id, permission_id=permission_id)
            .on_conflict_do_nothing(index_elements=["capability_id", "permission_id"])
        )


async def sync_capability_identities(
    db: AsyncSession,
    capabilities: Iterable[tuple[str, str]],
) -> dict[tuple[str, str], int]:
    normalized = sorted({(str(module), str(action)) for module, action in capabilities})
    if not normalized:
        return {}
    for module_key, action in normalized:
        await db.execute(
            insert(CapabilityIdentity)
            .values(module_key=module_key, action=action, permission_match_mode="all", enabled=True)
            .on_conflict_do_nothing(index_elements=["module_key", "action"])
        )
    rows = await db.execute(
        select(CapabilityIdentity).where(
            CapabilityIdentity.module_key.in_({module for module, _ in normalized}),
            CapabilityIdentity.enabled.is_(True),
        )
    )
    wanted = set(normalized)
    return {
        (row.module_key, row.action): int(row.id)
        for row in rows.scalars().all()
        if (row.module_key, row.action) in wanted
    }


async def allowed_capability_ids(
    db: AsyncSession,
    *,
    principal: PrincipalContext,
    capability_ids: Iterable[int],
) -> set[int]:
    requested = {int(value) for value in capability_ids}
    if not requested:
        return set()
    identities = list(
        (
            await db.execute(
                select(CapabilityIdentity).where(
                    CapabilityIdentity.id.in_(requested),
                    CapabilityIdentity.enabled.is_(True),
                )
            )
        ).scalars().all()
    )
    requirement_rows = (
        await db.execute(
            select(
                CapabilityPermissionRequirement.capability_id,
                CapabilityPermissionRequirement.permission_id,
            ).where(CapabilityPermissionRequirement.capability_id.in_(requested))
        )
    ).all()
    required_by_capability: dict[int, set[int]] = {}
    for capability_id, permission_id in requirement_rows:
        required_by_capability.setdefault(int(capability_id), set()).add(int(permission_id))
    granted = set(principal.permission_ids)
    allowed: set[int] = set()
    for identity in identities:
        required = required_by_capability.get(int(identity.id), set())
        if not required:
            allowed.add(int(identity.id))
        elif identity.permission_match_mode == "any" and required & granted:
            allowed.add(int(identity.id))
        elif identity.permission_match_mode == "all" and required <= granted:
            allowed.add(int(identity.id))
    return allowed


async def filter_authorized_capabilities(
    db: AsyncSession,
    *,
    principal: PrincipalContext,
    capabilities: list[dict],
) -> list[dict]:
    identity_map = await sync_capability_identities(
        db,
        ((item["module"], item["action"]) for item in capabilities),
    )
    await _sync_legacy_capability_requirements(
        db,
        capabilities=capabilities,
        identity_map=identity_map,
    )
    allowed_ids = await allowed_capability_ids(
        db,
        principal=principal,
        capability_ids=identity_map.values(),
    )
    result: list[dict] = []
    for item in capabilities:
        key = (str(item["module"]), str(item["action"]))
        capability_id = identity_map.get(key)
        if capability_id not in allowed_ids:
            continue
        result.append({
            **{key: value for key, value in item.items() if key != "legacy_min_role"},
            "capability_id": capability_id,
        })
    return result


async def assert_capability_authorized(
    db: AsyncSession,
    *,
    user_id: int,
    module_key: str,
    action: str,
    legacy_min_role: str = "viewer",
) -> PrincipalContext:
    principal = await resolve_principal_context(db, int(user_id))
    identity_map = await sync_capability_identities(db, [(module_key, action)])
    capability_id = identity_map.get((str(module_key), str(action)))
    if capability_id is None:
        raise PermissionDenied("Capability is not available")
    await _sync_legacy_capability_requirements(
        db,
        capabilities=[{
            "module": module_key,
            "action": action,
            "legacy_min_role": legacy_min_role,
        }],
        identity_map=identity_map,
    )
    allowed = await allowed_capability_ids(
        db,
        principal=principal,
        capability_ids=[capability_id],
    )
    if capability_id not in allowed:
        raise PermissionDenied("Capability is not available for the current user")
    return principal
