from fastapi import Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.services.auth import decode_access_token, get_user_by_id
from app.models.user import User
from app.core.exceptions import AuthError, PermissionDenied

security = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not credentials:
        raise AuthError("Authentication required")

    payload = decode_access_token(credentials.credentials)
    user_id = int(payload.get("sub", 0))
    token_sv = payload.get("sv", 0)
    user = await get_user_by_id(db, user_id)
    if not user or not user.enabled:
        raise AuthError("User not found or disabled")
    if token_sv != user.session_version:
        raise AuthError("Session expired, please login again")
    return user


ROLE_LEVEL = {"admin": 3, "editor": 2, "viewer": 1}
COLLAB_PERM_BITS = {"can_share", "can_publish", "can_reshare", "can_collab"}


def require_permission(min_role: str = "viewer"):
    """Dependency that checks the user's role.
    Role hierarchy: admin > editor > viewer
    """
    async def check_role(user: User = Depends(get_current_user)) -> User:
        if ROLE_LEVEL.get(user.role, 0) < ROLE_LEVEL.get(min_role, 0):
            raise PermissionDenied(
                f"Requires at least '{min_role}' role, got '{user.role}'"
            )
        return user

    return check_role


async def check_collab_permission(
    db: AsyncSession,
    user: User,
    perm_bit: str,
) -> bool:
    """Check if a user has a specific collaboration permission bit from the role matrix."""
    if perm_bit not in COLLAB_PERM_BITS:
        return False
    from app.services.role_service import get_role_matrix
    matrix = await get_role_matrix(db)
    for entry in matrix:
        if entry["role_key"] == user.role:
            return bool(entry["permissions"].get(perm_bit, False))
    return False


def require_collab_permission(perm_bit: str):
    """Dependency that checks a collaboration-specific permission bit."""
    if perm_bit not in COLLAB_PERM_BITS:
        raise ValueError(f"Unknown collaboration permission bit: {perm_bit}")

    async def check(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> User:
        has_perm = await check_collab_permission(db, user, perm_bit)
        if not has_perm:
            raise PermissionDenied(
                f"User role '{user.role}' lacks collaboration permission '{perm_bit}'"
            )
        return user

    return check
