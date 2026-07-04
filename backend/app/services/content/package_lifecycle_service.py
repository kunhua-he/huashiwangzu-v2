"""ContentPackage source-file lifecycle handling."""

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationError
from app.models.content import ContentPackage, ContentPackageVersion
from app.models.file import File

SOURCE_AVAILABLE = "source_available"
SOURCE_RECYCLED = "source_recycled"
SOURCE_MISSING = "source_missing"
SOURCE_PERMANENTLY_DELETED = "source_permanently_deleted"

SOURCE_FILE_DELETED_REASON = "source_file_deleted"
SOURCE_FILE_MISSING_REASON = "source_file_missing"
SOURCE_FILE_PERMANENTLY_DELETED_REASON = "source_file_permanently_deleted"
TEST_DATA_CLEANUP_ARCHIVE_REASON = "archived_by_test_data_cleanup"
CONFIRM_ARCHIVE_LIFECYCLE_UNAVAILABLE_PACKAGES = "ARCHIVE_LIFECYCLE_UNAVAILABLE_PACKAGES"
CONFIRM_REPAIR_CONTENT_CURRENT_VERSION = "REPAIR_CONTENT_CURRENT_VERSION"
VERSION_REQUIRED_STATUSES = {"parsed", "degraded", "partial"}
ARCHIVED_LIFECYCLE_REASONS = {
    SOURCE_FILE_DELETED_REASON,
    SOURCE_FILE_MISSING_REASON,
    SOURCE_FILE_PERMANENTLY_DELETED_REASON,
    TEST_DATA_CLEANUP_ARCHIVE_REASON,
}
LIFECYCLE_REASONS = {
    "source_unavailable",
    SOURCE_FILE_DELETED_REASON,
    SOURCE_FILE_MISSING_REASON,
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_manifest(pkg: ContentPackage) -> dict[str, Any]:
    if not pkg.manifest_json:
        return {}
    try:
        data = json.loads(pkg.manifest_json)
    except (json.JSONDecodeError, TypeError):
        return {}
    return data if isinstance(data, dict) else {}


def _store_manifest(pkg: ContentPackage, manifest: dict[str, Any]) -> None:
    pkg.manifest_json = json.dumps(manifest, ensure_ascii=False)


def _lifecycle_from_package_and_file(pkg: ContentPackage, file: File | None) -> tuple[str, bool, str | None]:
    if not pkg.source_file_id:
        return SOURCE_MISSING, False, SOURCE_FILE_MISSING_REASON
    if file is None:
        if pkg.parse_error == SOURCE_FILE_PERMANENTLY_DELETED_REASON:
            return SOURCE_PERMANENTLY_DELETED, False, SOURCE_FILE_PERMANENTLY_DELETED_REASON
        return SOURCE_MISSING, False, SOURCE_FILE_MISSING_REASON
    if file.deleted:
        return SOURCE_RECYCLED, False, SOURCE_FILE_DELETED_REASON
    return SOURCE_AVAILABLE, True, None


def apply_lifecycle_metadata(
    pkg: ContentPackage,
    *,
    lifecycle_state: str,
    reason: str | None,
    archived: bool,
    restored: bool = False,
    audit_reason: str = "",
) -> None:
    manifest = _load_manifest(pkg)
    lifecycle = manifest.get("lifecycle")
    if not isinstance(lifecycle, dict):
        lifecycle = {}
    if archived and not lifecycle.get("previous_status") and pkg.status != "archived":
        lifecycle["previous_status"] = pkg.status
    lifecycle.update({
        "source_lifecycle_state": lifecycle_state,
        "source_available": lifecycle_state == SOURCE_AVAILABLE,
        "archived_by_lifecycle": archived,
        "reason": reason,
        "updated_at": _utc_now(),
    })
    if audit_reason:
        lifecycle["audit_reason"] = audit_reason
    if restored:
        lifecycle["restored"] = True
        lifecycle["restored_at"] = _utc_now()
    manifest["lifecycle"] = lifecycle
    _store_manifest(pkg, manifest)


def package_lifecycle_fields(pkg: ContentPackage) -> dict[str, Any]:
    manifest = _load_manifest(pkg)
    lifecycle = manifest.get("lifecycle") if isinstance(manifest, dict) else None
    lifecycle = lifecycle if isinstance(lifecycle, dict) else {}
    state = lifecycle.get("source_lifecycle_state")
    reason = lifecycle.get("reason")
    if not state:
        if pkg.parse_error == SOURCE_FILE_PERMANENTLY_DELETED_REASON:
            state = SOURCE_PERMANENTLY_DELETED
            reason = SOURCE_FILE_PERMANENTLY_DELETED_REASON
        elif pkg.parse_error == SOURCE_FILE_DELETED_REASON:
            state = SOURCE_RECYCLED
            reason = SOURCE_FILE_DELETED_REASON
        elif pkg.parse_error == SOURCE_FILE_MISSING_REASON:
            state = SOURCE_MISSING
            reason = SOURCE_FILE_MISSING_REASON
        elif pkg.source_file_id:
            state = SOURCE_AVAILABLE
        else:
            state = SOURCE_MISSING
            reason = SOURCE_FILE_MISSING_REASON
    return {
        "source_lifecycle_state": state,
        "source_available": state == SOURCE_AVAILABLE,
        "archived_by_lifecycle": bool(
            lifecycle.get("archived_by_lifecycle")
            or (pkg.status == "archived" and pkg.parse_error in ARCHIVED_LIFECYCLE_REASONS)
        ),
        "lifecycle_reason": reason,
    }


async def audit_content_package_lifecycle_debt(db: AsyncSession, *, limit: int = 20) -> dict[str, Any]:
    base = ContentPackage.deleted.is_(False)
    active_packages = await db.scalar(select(func.count(ContentPackage.id)).where(base)) or 0
    source_recycled = await db.scalar(
        select(func.count(ContentPackage.id))
        .join(File, File.id == ContentPackage.source_file_id)
        .where(base, File.deleted.is_(True))
    ) or 0
    source_missing = await db.scalar(
        select(func.count(ContentPackage.id))
        .outerjoin(File, File.id == ContentPackage.source_file_id)
        .where(base, ContentPackage.source_file_id.is_not(None), File.id.is_(None))
    ) or 0
    archived_by_lifecycle = await db.scalar(
        select(func.count(ContentPackage.id)).where(
            base,
            ContentPackage.status == "archived",
            ContentPackage.parse_error.in_(ARCHIVED_LIFECYCLE_REASONS),
        )
    ) or 0
    unarchived_source_unavailable = await db.scalar(
        select(func.count(ContentPackage.id))
        .outerjoin(File, File.id == ContentPackage.source_file_id)
        .where(
            base,
            ContentPackage.source_file_id.is_not(None),
            ((File.id.is_(None)) | (File.deleted.is_(True))),
            ~(
                (ContentPackage.status == "archived")
                & ContentPackage.parse_error.in_(ARCHIVED_LIFECYCLE_REASONS)
            ),
        )
    ) or 0
    missing_current_version_blockers = await db.scalar(
        select(func.count(ContentPackage.id)).where(
            base,
            ContentPackage.current_version_id.is_(None),
            ContentPackage.source_file_id.is_not(None),
            ContentPackage.status.in_(VERSION_REQUIRED_STATUSES),
            ContentPackage.status != "archived",
        )
    ) or 0
    sample_rows = await db.execute(
        select(ContentPackage, File)
        .outerjoin(File, File.id == ContentPackage.source_file_id)
        .where(
            base,
            ContentPackage.source_file_id.is_not(None),
            (File.id.is_(None)) | (File.deleted.is_(True)),
        )
        .order_by(ContentPackage.id.desc())
        .limit(limit)
    )
    samples = []
    candidate_ids = []
    for pkg, file in sample_rows.all():
        state, available, reason = _lifecycle_from_package_and_file(pkg, file)
        candidate_ids.append(pkg.id)
        samples.append({
            "package_id": pkg.id,
            "source_file_id": pkg.source_file_id,
            "status": pkg.status,
            "source_lifecycle_state": state,
            "source_available": available,
            "reason": reason,
            "archived_by_lifecycle": pkg.status == "archived" and pkg.parse_error in ARCHIVED_LIFECYCLE_REASONS,
        })
    return {
        "active_packages": active_packages,
        "source_recycled_count": source_recycled,
        "source_missing_count": source_missing,
        "source_unavailable_count": source_recycled + source_missing,
        "archived_by_lifecycle_count": archived_by_lifecycle,
        "unarchived_source_unavailable_count": unarchived_source_unavailable,
        "missing_current_version_blocker_count": missing_current_version_blockers,
        "candidate_package_ids": candidate_ids,
        "sample_packages": samples,
        "recommended_action": "Archive lifecycle-unavailable packages; restore source files before editing or publishing.",
    }


def _validate_lifecycle_reason(reason: str | None) -> str:
    normalized = str(reason or "source_unavailable")
    if normalized not in LIFECYCLE_REASONS:
        raise ValidationError("reason must be source_unavailable, source_file_deleted, or source_file_missing")
    return normalized


def _reason_matches(state_reason: str | None, requested_reason: str) -> bool:
    if requested_reason == "source_unavailable":
        return state_reason in {SOURCE_FILE_DELETED_REASON, SOURCE_FILE_MISSING_REASON}
    return state_reason == requested_reason


async def _source_unavailable_packages(
    db: AsyncSession,
    *,
    limit: int,
    reason: str | None = None,
) -> list[tuple[ContentPackage, File | None, str, str]]:
    requested_reason = _validate_lifecycle_reason(reason)
    rows = await db.execute(
        select(ContentPackage, File)
        .outerjoin(File, File.id == ContentPackage.source_file_id)
        .where(
            ContentPackage.deleted.is_(False),
            ContentPackage.source_file_id.is_not(None),
            (File.id.is_(None)) | (File.deleted.is_(True)),
            ~(
                (ContentPackage.status == "archived")
                & ContentPackage.parse_error.in_(ARCHIVED_LIFECYCLE_REASONS)
            ),
        )
        .order_by(ContentPackage.id.desc())
        .limit(max(1, min(int(limit or 100), 5000)))
    )
    packages: list[tuple[ContentPackage, File | None, str, str]] = []
    for pkg, file in rows.all():
        state, _available, state_reason = _lifecycle_from_package_and_file(pkg, file)
        state_reason = state_reason or SOURCE_FILE_MISSING_REASON
        if not _reason_matches(state_reason, requested_reason):
            continue
        packages.append((pkg, file, state, state_reason))
    return packages


def _package_lifecycle_item(pkg: ContentPackage, file: File | None, state: str, reason: str) -> dict[str, Any]:
    return {
        "package_id": int(pkg.id),
        "source_file_id": int(pkg.source_file_id) if pkg.source_file_id else None,
        "status": pkg.status,
        "parse_error": pkg.parse_error,
        "source_lifecycle_state": state,
        "reason": reason,
        "source_file_deleted": bool(file.deleted) if file is not None else None,
        "archived_by_lifecycle": pkg.status == "archived" and pkg.parse_error in ARCHIVED_LIFECYCLE_REASONS,
    }


async def archive_lifecycle_unavailable_packages(
    db: AsyncSession,
    *,
    dry_run: bool = True,
    limit: int = 100,
    reason: str | None = None,
    confirm: str = "",
    audit_reason: str = "",
) -> dict[str, Any]:
    packages = await _source_unavailable_packages(db, limit=limit, reason=reason)
    items = [_package_lifecycle_item(pkg, file, state, state_reason) for pkg, file, state, state_reason in packages]
    summary = {
        SOURCE_FILE_DELETED_REASON: sum(1 for item in items if item["reason"] == SOURCE_FILE_DELETED_REASON),
        SOURCE_FILE_MISSING_REASON: sum(1 for item in items if item["reason"] == SOURCE_FILE_MISSING_REASON),
    }
    if dry_run:
        return {
            "dry_run": True,
            "action": "archive_lifecycle_unavailable_packages",
            "matched": len(items),
            "selected": len(items),
            "changed": 0,
            "summary": summary,
            "candidate_package_ids": [item["package_id"] for item in items],
            "sample_packages": items[:20],
            "requires_confirm": True,
            "confirm_token": CONFIRM_ARCHIVE_LIFECYCLE_UNAVAILABLE_PACKAGES,
            "reason": audit_reason,
        }
    if confirm != CONFIRM_ARCHIVE_LIFECYCLE_UNAVAILABLE_PACKAGES:
        raise ValidationError("confirm must be ARCHIVE_LIFECYCLE_UNAVAILABLE_PACKAGES to archive lifecycle packages")

    changed = 0
    changed_items = []
    for pkg, file, state, state_reason in packages:
        already_archived = pkg.status == "archived" and pkg.parse_error == state_reason
        apply_lifecycle_metadata(
            pkg,
            lifecycle_state=state,
            reason=state_reason,
            archived=True,
            audit_reason=audit_reason,
        )
        pkg.status = "archived"
        pkg.parse_error = state_reason
        if not already_archived:
            changed += 1
        changed_items.append(_package_lifecycle_item(pkg, file, state, state_reason))
    await db.commit()
    return {
        "dry_run": False,
        "action": "archive_lifecycle_unavailable_packages",
        "matched": len(items),
        "selected": len(items),
        "changed": changed,
        "summary": summary,
        "changed_items": changed_items,
        "reason": audit_reason,
    }


async def repair_missing_current_versions(
    db: AsyncSession,
    *,
    dry_run: bool = True,
    limit: int = 100,
    confirm: str = "",
) -> dict[str, Any]:
    limit = max(1, min(int(limit or 100), 5000))
    rows = await db.execute(
        select(ContentPackage)
        .where(
            ContentPackage.deleted.is_(False),
            ContentPackage.current_version_id.is_(None),
            ContentPackage.status.in_(VERSION_REQUIRED_STATUSES),
        )
        .order_by(ContentPackage.id.desc())
        .limit(limit)
    )
    packages = rows.scalars().all()
    repairable = []
    unrepairable = []
    ignored = []
    for pkg in packages:
        if not pkg.source_file_id:
            ignored.append({"package_id": int(pkg.id), "reason": "without_source_file_id"})
            continue
        latest = await db.scalar(
            select(ContentPackageVersion)
            .where(ContentPackageVersion.package_id == pkg.id)
            .order_by(ContentPackageVersion.version_no.desc(), ContentPackageVersion.id.desc())
            .limit(1)
        )
        if latest:
            repairable.append({"package": pkg, "version": latest})
        else:
            unrepairable.append({"package_id": int(pkg.id), "reason": "no_versions"})

    if dry_run:
        return {
            "dry_run": True,
            "action": "repair_missing_current_versions",
            "matched": len(packages),
            "repairable": len(repairable),
            "unrepairable": len(unrepairable),
            "ignored": len(ignored),
            "candidate_package_ids": [int(item["package"].id) for item in repairable],
            "unrepairable_items": unrepairable,
            "ignored_items": ignored,
            "changed": 0,
            "requires_confirm": True,
            "confirm_token": CONFIRM_REPAIR_CONTENT_CURRENT_VERSION,
        }
    if confirm != CONFIRM_REPAIR_CONTENT_CURRENT_VERSION:
        raise ValidationError("confirm must be REPAIR_CONTENT_CURRENT_VERSION to repair current versions")

    for item in repairable:
        item["package"].current_version_id = item["version"].id
    await db.commit()
    return {
        "dry_run": False,
        "action": "repair_missing_current_versions",
        "matched": len(packages),
        "changed": len(repairable),
        "repaired_package_ids": [int(item["package"].id) for item in repairable],
        "unrepairable_items": unrepairable,
        "ignored_items": ignored,
    }


async def handle_file_deleted(db: AsyncSession, file_id: int) -> dict[str, Any]:
    return await _archive_for_lifecycle(
        db,
        file_id=file_id,
        lifecycle_state=SOURCE_RECYCLED,
        reason=SOURCE_FILE_DELETED_REASON,
    )


async def handle_file_permanently_deleted(db: AsyncSession, file_id: int) -> dict[str, Any]:
    return await _archive_for_lifecycle(
        db,
        file_id=file_id,
        lifecycle_state=SOURCE_PERMANENTLY_DELETED,
        reason=SOURCE_FILE_PERMANENTLY_DELETED_REASON,
    )


async def _archive_for_lifecycle(
    db: AsyncSession,
    *,
    file_id: int,
    lifecycle_state: str,
    reason: str,
) -> dict[str, Any]:
    result = await db.execute(
        select(ContentPackage).where(
            ContentPackage.source_file_id == file_id,
            ContentPackage.deleted.is_(False),
        )
    )
    packages = result.scalars().all()
    changed = 0
    for pkg in packages:
        already_archived = pkg.status == "archived" and pkg.parse_error == reason
        apply_lifecycle_metadata(
            pkg,
            lifecycle_state=lifecycle_state,
            reason=reason,
            archived=True,
        )
        if not already_archived:
            changed += 1
        pkg.status = "archived"
        pkg.parse_error = reason
    await db.commit()
    return {
        "file_id": file_id,
        "matched_packages": len(packages),
        "changed_packages": changed,
        "status": "archived_by_lifecycle",
        "reason": reason,
    }


async def handle_file_restored(db: AsyncSession, file_id: int) -> dict[str, Any]:
    file = await db.get(File, file_id)
    if not file or file.deleted:
        return {
            "file_id": file_id,
            "matched_packages": 0,
            "changed_packages": 0,
            "status": "skipped",
            "reason": SOURCE_FILE_MISSING_REASON,
        }
    result = await db.execute(
        select(ContentPackage).where(
            ContentPackage.source_file_id == file_id,
            ContentPackage.deleted.is_(False),
        )
    )
    packages = result.scalars().all()
    changed = 0
    for pkg in packages:
        manifest = _load_manifest(pkg)
        lifecycle = manifest.get("lifecycle") if isinstance(manifest, dict) else {}
        lifecycle = lifecycle if isinstance(lifecycle, dict) else {}
        previous_status = str(lifecycle.get("previous_status") or "parsed")
        was_archived = pkg.status == "archived" or bool(lifecycle.get("archived_by_lifecycle"))
        apply_lifecycle_metadata(
            pkg,
            lifecycle_state=SOURCE_AVAILABLE,
            reason=None,
            archived=False,
            restored=True,
        )
        if pkg.parse_error in {
            SOURCE_FILE_DELETED_REASON,
            SOURCE_FILE_MISSING_REASON,
            SOURCE_FILE_PERMANENTLY_DELETED_REASON,
            TEST_DATA_CLEANUP_ARCHIVE_REASON,
        }:
            pkg.parse_error = None
        if was_archived:
            pkg.status = previous_status if previous_status != "archived" else "parsed"
            changed += 1
    await db.commit()
    return {
        "file_id": file_id,
        "matched_packages": len(packages),
        "changed_packages": changed,
        "status": "restored",
        "reason": "source_file_restored",
    }
