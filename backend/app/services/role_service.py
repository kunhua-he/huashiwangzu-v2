import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.role_matrix import RoleMatrix
from app.core.exceptions import NotFound, ValidationError

logger = logging.getLogger("v2.role")

DEFAULT_MATRIX = [
    {
        "role_key": "admin",
        "display_name": "管理员",
        "permissions": {
            "user_management": True,
            "system_config": True,
            "role_matrix": True,
            "can_share": True,
            "can_publish": True,
            "can_reshare": True,
            "can_collab": True,
        },
    },
    {
        "role_key": "editor",
        "display_name": "编辑者",
        "permissions": {
            "user_management": False,
            "system_config": False,
            "role_matrix": False,
            "can_share": True,
            "can_publish": False,
            "can_reshare": False,
            "can_collab": True,
        },
    },
    {
        "role_key": "viewer",
        "display_name": "查看者",
        "permissions": {
            "user_management": False,
            "system_config": False,
            "role_matrix": False,
            "can_share": False,
            "can_publish": False,
            "can_reshare": False,
            "can_collab": False,
        },
    },
]

VALID_ROLES = ["admin", "editor", "viewer"]


async def get_role_matrix(db: AsyncSession) -> list[dict]:
    result = await db.execute(select(RoleMatrix).order_by(RoleMatrix.id))
    rows = result.scalars().all()
    if not rows:
        return _seed_default_matrix(db, DEFAULT_MATRIX)

    # Merge default collab permission bits into existing rows (backward compat)
    default_perms_by_role = {m["role_key"]: m["permissions"] for m in DEFAULT_MATRIX}
    output = []
    for r in rows:
        perms = dict(r.permissions or {})
        defaults = default_perms_by_role.get(r.role_key, {})
        for k, v in defaults.items():
            perms.setdefault(k, v)
        output.append({"role_key": r.role_key, "display_name": r.display_name, "permissions": perms})
    return output


async def update_role_matrix(db: AsyncSession, matrix: list[dict]) -> list[dict]:
    for item in matrix:
        role_key = item.get("role_key", "")
        if role_key not in VALID_ROLES:
            raise ValidationError(f"Invalid role_key: {role_key}, valid: {', '.join(VALID_ROLES)}")

    existing = await db.execute(select(RoleMatrix))
    existing_rows = {r.role_key: r for r in existing.scalars().all()}

    for item in matrix:
        role_key = item["role_key"]
        if role_key in existing_rows:
            row = existing_rows[role_key]
            row.display_name = item.get("display_name", row.display_name)
            row.permissions = item.get("permissions", row.permissions)
        else:
            row = RoleMatrix(role_key=role_key, display_name=item.get("display_name", ""), permissions=item.get("permissions", {}))
            db.add(row)

    await db.commit()

    return await get_role_matrix(db)


async def _seed_default_matrix(db: AsyncSession, defaults: list[dict]) -> list[dict]:
    for item in defaults:
        row = RoleMatrix(role_key=item["role_key"], display_name=item["display_name"], permissions=item["permissions"])
        db.add(row)
    await db.commit()
    return defaults