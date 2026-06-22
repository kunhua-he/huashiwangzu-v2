from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exceptions import PermissionDenied, AppException
from .models import DocsOpenToken, generate_access_token


async def create_token(
    db: AsyncSession,
    client_id: str,
    open_id: int,
    scope: dict | None = None,
    expiry_hours: int = 2,
) -> dict:
    """Create a new document access token.
    
    Returns dict with client_id, open_id, access_token, scope, expires_at.
    """
    raw, prefix, hashed = generate_access_token()

    token = DocsOpenToken(
        client_id=client_id,
        open_id=open_id,
        access_token_hash=hashed,
        token_prefix=prefix,
        scope=scope or {},
        expires_at=datetime.now(timezone.utc) + timedelta(hours=expiry_hours),
    )
    db.add(token)
    await db.commit()
    await db.refresh(token)

    return {
        "client_id": client_id,
        "open_id": str(open_id),
        "access_token": f"{prefix}.{raw}",
        "scope": scope or {},
        "expires_at": token.expires_at.isoformat(),
        "token_id": token.id,
    }


async def validate_token(
    db: AsyncSession,
    access_token: str,
    client_id: str,
    open_id: str,
) -> DocsOpenToken:
    """Validate a token. Returns the token record or raises."""
    parts = access_token.split(".", 1)
    if len(parts) != 2:
        raise PermissionDenied("Invalid token format")

    prefix, raw = parts
    _, _, hashed = generate_access_token()
    # Re-hash the raw part to compare
    import uuid
    test_hash = uuid.uuid5(uuid.NAMESPACE_DNS, raw).hex

    result = await db.execute(
        select(DocsOpenToken).where(
            DocsOpenToken.token_prefix == prefix,
            DocsOpenToken.access_token_hash == test_hash,
            DocsOpenToken.is_revoked == False,
        )
    )
    token = result.scalar_one_or_none()
    if not token:
        raise PermissionDenied("Token not found or revoked")

    if token.client_id != client_id:
        raise PermissionDenied("Client-Id mismatch")

    if str(token.open_id) != open_id:
        raise PermissionDenied("Open-Id mismatch")

    if token.expires_at < datetime.now(timezone.utc):
        raise PermissionDenied("Token expired")

    return token


def check_doc_access(token: DocsOpenToken, doc_id: int) -> bool:
    """Check if token has access to a specific doc.
    If scope has doc_ids list, check membership.
    If scope is empty or has 'all_docs', allow access.
    """
    scope = token.scope or {}
    doc_ids = scope.get("doc_ids")
    if doc_ids is None:
        return True
    if isinstance(doc_ids, list):
        return doc_id in doc_ids
    return True
