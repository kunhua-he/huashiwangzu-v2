"""Office router — bridges old /api/office/* endpoints to Content Package API.
Legacy compatibility layer: maps old JSON Package semantics to Content Package.
Deprecated endpoints (patch/preview/apply/rollback) removed — use
Content Package versions and restore instead.
"""
import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.schemas.common import ApiResponse
from app.middleware.auth import require_permission
from app.models.user import User

logger = logging.getLogger("v2.content").getChild("office_router")

router = APIRouter(prefix="/api/office", tags=["office"])


async def _get_content_package_for_file(db: AsyncSession, file_id: int, user_id: int) -> dict | None:
    """Look up Content Package by source file, permissions checked by owner."""
    from app.models.content import ContentPackage
    from sqlalchemy import select
    r = await db.execute(
        select(ContentPackage).where(
            ContentPackage.source_file_id == file_id,
            ContentPackage.deleted.is_(False),
        ).order_by(ContentPackage.created_at.desc()).limit(1)
    )
    pkg = r.scalar_one_or_none()
    if not pkg:
        return None
    return {
        "id": pkg.id,
        "file_id": pkg.source_file_id,
        "current_version_id": pkg.current_version_id,
        "format_type": pkg.source_extension or "txt",
        "package_status": pkg.status,
    }


async def _require_file_access(db: AsyncSession, file_id: int, user_id: int):
    """Return the File record (ORM) or raise NotFound/PermissionDenied."""
    from app.services.file_service import check_file_access
    return await check_file_access(db, file_id, user_id)


async def _require_package_access(db: AsyncSession, package_id: int, user_id: int) -> dict:
    from app.services.content.package_service import ContentPackageService
    svc = ContentPackageService()
    try:
        pkg = await svc.get_package(db, package_id=package_id, owner_id=user_id)
        return pkg
    except Exception as e:
        from app.core.exceptions import NotFound
        raise NotFound(f"Package not found: {e}") from e


@router.get("/status/{file_id}")
async def get_status(
    file_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("viewer")),
):
    file = await _require_file_access(db, file_id, user.id)
    pkg = await _get_content_package_for_file(db, file_id, user.id)
    return ApiResponse(data={
        "file_id": file_id,
        "file_name": f"{file.name}.{file.extension}",
        "has_package": pkg is not None,
        "package_id": pkg["id"] if pkg else None,
        "current_version_id": pkg["current_version_id"] if pkg else None,
        "package_status": pkg["package_status"] if pkg else "not_generated",
        "format_type": pkg["format_type"] if pkg else None,
    })


@router.post("/package")
async def create_package(
    file_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("editor")),
):
    await _require_file_access(db, file_id, user.id)
    from app.services.content.package_service import ContentPackageService
    svc = ContentPackageService()
    result = await svc.get_or_create(db, file_id, user.id, f"user:{user.id}")
    return ApiResponse(data={
        "id": result["id"],
        "file_id": result["source_file_id"],
        "current_version_id": result["current_version_id"],
        "format_type": result["source_extension"],
        "package_status": result["status"],
    })


@router.get("/package/{package_id}")
async def read_package(
    package_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("viewer")),
):
    pkg = await _require_package_access(db, package_id, user.id)
    return ApiResponse(data={
        "id": pkg["id"],
        "file_id": pkg["source_file_id"],
        "current_version_id": pkg["current_version_id"],
        "format_type": pkg["source_extension"],
        "package_status": pkg["status"],
    })


@router.get("/package/{package_id}/versions")
async def list_versions(
    package_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("viewer")),
):
    await _require_package_access(db, package_id, user.id)
    from app.services.content.package_service import ContentPackageService
    svc = ContentPackageService()
    versions = await svc.list_versions(db, package_id, owner_id=user.id)
    return ApiResponse(data=[
        {
            "id": v["id"],
            "package_id": v["package_id"],
            "version_number": v["version_no"],
            "summary": v["summary"],
            "creator_id": v["created_by"],
            "created_at": str(v["created_at"]) if v.get("created_at") else None,
        }
        for v in versions
    ])



