"""ContentPackage source-file lifecycle tests."""

import json
import uuid

import app.main  # noqa: F401 - registers content event handlers/capabilities
import pytest
from app.database import AsyncSessionLocal
from app.models.content import ContentPackage, ContentPackageVersion
from app.models.file import File
from app.services.content.package_lifecycle_service import (
    archive_lifecycle_unavailable_packages,
    audit_content_package_lifecycle_debt,
    handle_file_deleted,
    handle_file_permanently_deleted,
    handle_file_restored,
    repair_missing_current_versions,
)
from app.services.content.package_service import ContentPackageService
from sqlalchemy import delete


async def _cleanup(file_id: int | None, package_id: int | None) -> None:
    async with AsyncSessionLocal() as db:
        if package_id:
            await db.execute(delete(ContentPackageVersion).where(ContentPackageVersion.package_id == package_id))
            await db.execute(delete(ContentPackage).where(ContentPackage.id == package_id))
        if file_id:
            await db.execute(delete(File).where(File.id == file_id))
        await db.commit()


@pytest.mark.asyncio
async def test_content_package_archives_and_restores_with_source_file_lifecycle() -> None:
    owner_id = 4
    file_id = None
    package_id = None
    async with AsyncSessionLocal() as db:
        file = File(
            name=f"lifecycle-source-{uuid.uuid4().hex}",
            extension="txt",
            size=0,
            owner_id=owner_id,
            storage_path="lifecycle-source.txt",
            mime_type="text/plain",
            deleted=False,
        )
        db.add(file)
        await db.flush()
        package = ContentPackage(
            owner_id=owner_id,
            source_file_id=file.id,
            package_type="text",
            origin_type="generated",
            source_extension="txt",
            status="parsed",
            manifest_json=json.dumps({"title": "Lifecycle"}, ensure_ascii=False),
        )
        db.add(package)
        await db.flush()
        file_id = file.id
        package_id = package.id
        await db.commit()

    try:
        async with AsyncSessionLocal() as db:
            deleted_result = await handle_file_deleted(db, file_id)
            package = await db.get(ContentPackage, package_id)
            assert deleted_result["matched_packages"] == 1
            assert package is not None
            assert package.deleted is False
            assert package.status == "archived"
            assert package.parse_error == "source_file_deleted"
            payload = ContentPackageService()._package_to_dict(package)
            assert payload["source_lifecycle_state"] == "source_recycled"
            assert payload["archived_by_lifecycle"] is True

        async with AsyncSessionLocal() as db:
            restored_result = await handle_file_restored(db, file_id)
            package = await db.get(ContentPackage, package_id)
            assert restored_result["changed_packages"] == 1
            assert package is not None
            assert package.status == "parsed"
            assert package.parse_error is None
            payload = ContentPackageService()._package_to_dict(package)
            assert payload["source_lifecycle_state"] == "source_available"
            assert payload["archived_by_lifecycle"] is False
    finally:
        await _cleanup(file_id, package_id)


@pytest.mark.asyncio
async def test_content_package_permanent_delete_event_is_idempotent_archive() -> None:
    owner_id = 4
    file_id = None
    package_id = None
    async with AsyncSessionLocal() as db:
        file = File(
            name=f"permanent-source-{uuid.uuid4().hex}",
            extension="txt",
            size=0,
            owner_id=owner_id,
            storage_path="permanent-source.txt",
            mime_type="text/plain",
            deleted=True,
        )
        db.add(file)
        await db.flush()
        package = ContentPackage(
            owner_id=owner_id,
            source_file_id=file.id,
            package_type="text",
            origin_type="generated",
            source_extension="txt",
            status="parsed",
        )
        db.add(package)
        await db.flush()
        file_id = file.id
        package_id = package.id
        await db.commit()

    try:
        async with AsyncSessionLocal() as db:
            first = await handle_file_permanently_deleted(db, file_id)
            second = await handle_file_permanently_deleted(db, file_id)
            package = await db.get(ContentPackage, package_id)
            assert first["matched_packages"] == 1
            assert second["matched_packages"] == 1
            assert second["changed_packages"] == 0
            assert package is not None
            assert package.deleted is False
            assert package.status == "archived"
            assert package.parse_error == "source_file_permanently_deleted"
            payload = ContentPackageService()._package_to_dict(package)
            assert payload["source_lifecycle_state"] == "source_permanently_deleted"
            assert payload["source_available"] is False
    finally:
        await _cleanup(file_id, package_id)


@pytest.mark.asyncio
async def test_archive_lifecycle_unavailable_packages_requires_confirm_and_archives() -> None:
    owner_id = 4
    file_id = None
    package_id = None
    async with AsyncSessionLocal() as db:
        file = File(
            name=f"archive-source-{uuid.uuid4().hex}",
            extension="txt",
            size=0,
            owner_id=owner_id,
            storage_path="archive-source.txt",
            mime_type="text/plain",
            deleted=True,
        )
        db.add(file)
        await db.flush()
        package = ContentPackage(
            owner_id=owner_id,
            source_file_id=file.id,
            package_type="text",
            origin_type="generated",
            source_extension="txt",
            status="parsed",
            manifest_json=json.dumps({"title": "Archive"}, ensure_ascii=False),
        )
        db.add(package)
        await db.flush()
        file_id = file.id
        package_id = package.id
        await db.commit()

    try:
        async with AsyncSessionLocal() as db:
            dry_run = await archive_lifecycle_unavailable_packages(db, dry_run=True, limit=1)
            assert package_id in dry_run["candidate_package_ids"]
            with pytest.raises(Exception, match="ARCHIVE_LIFECYCLE_UNAVAILABLE_PACKAGES"):
                await archive_lifecycle_unavailable_packages(
                    db,
                    dry_run=False,
                    limit=1,
                    confirm="WRONG",
                )

        async with AsyncSessionLocal() as db:
            result = await archive_lifecycle_unavailable_packages(
                db,
                dry_run=False,
                limit=1,
                confirm="ARCHIVE_LIFECYCLE_UNAVAILABLE_PACKAGES",
                audit_reason="cleanup-test",
            )
            package = await db.get(ContentPackage, package_id)
            assert result["changed"] >= 1
            assert package is not None
            assert package.status == "archived"
            assert package.parse_error == "source_file_deleted"
            manifest = json.loads(package.manifest_json or "{}")
            assert manifest["lifecycle"]["archived_by_lifecycle"] is True
            assert manifest["lifecycle"]["previous_status"] == "parsed"
            assert manifest["lifecycle"]["audit_reason"] == "cleanup-test"
    finally:
        await _cleanup(file_id, package_id)


@pytest.mark.asyncio
async def test_test_data_cleanup_archive_counts_as_lifecycle_archive() -> None:
    owner_id = 4
    file_id = None
    package_id = None
    async with AsyncSessionLocal() as db:
        file = File(
            name=f"test-pollution-source-{uuid.uuid4().hex}",
            extension="txt",
            size=0,
            owner_id=owner_id,
            storage_path="test-pollution-source.txt",
            mime_type="text/plain",
            deleted=True,
        )
        db.add(file)
        await db.flush()
        package = ContentPackage(
            owner_id=owner_id,
            source_file_id=file.id,
            package_type="text",
            origin_type="generated",
            source_extension="txt",
            status="archived",
            parse_error="archived_by_test_data_cleanup",
        )
        db.add(package)
        await db.flush()
        file_id = file.id
        package_id = package.id
        await db.commit()

    try:
        async with AsyncSessionLocal() as db:
            audit = await audit_content_package_lifecycle_debt(db, limit=5000)
            assert package_id in audit["candidate_package_ids"]
            assert audit["archived_by_lifecycle_count"] >= 1
            assert all(
                item["package_id"] != package_id or item["archived_by_lifecycle"] is True
                for item in audit["sample_packages"]
            )
    finally:
        await _cleanup(file_id, package_id)


@pytest.mark.asyncio
async def test_repair_missing_current_versions_repairs_only_versioned_packages() -> None:
    owner_id = 4
    repair_package_id = None
    ignored_package_id = None
    async with AsyncSessionLocal() as db:
        file = File(
            name=f"repair-source-{uuid.uuid4().hex}",
            extension="txt",
            size=0,
            owner_id=owner_id,
            storage_path="repair-source.txt",
            mime_type="text/plain",
            deleted=False,
        )
        db.add(file)
        await db.flush()
        repair_package = ContentPackage(
            owner_id=owner_id,
            source_file_id=file.id,
            package_type="text",
            origin_type="generated",
            source_extension="txt",
            status="parsed",
        )
        ignored_package = ContentPackage(
            owner_id=owner_id,
            source_file_id=None,
            package_type="text",
            origin_type="generated",
            source_extension="txt",
            status="parsed",
        )
        db.add_all([repair_package, ignored_package])
        await db.flush()
        version = ContentPackageVersion(
            package_id=repair_package.id,
            version_no=1,
            content_json=json.dumps({"manifest": {}, "blocks": []}),
            operation_type="parse",
            created_by=owner_id,
        )
        db.add(version)
        await db.flush()
        file_id = file.id
        repair_package_id = repair_package.id
        ignored_package_id = ignored_package.id
        await db.commit()

    try:
        async with AsyncSessionLocal() as db:
            dry_run = await repair_missing_current_versions(db, dry_run=True, limit=2)
            assert repair_package_id in dry_run["candidate_package_ids"]
            assert any(item["package_id"] == ignored_package_id for item in dry_run["ignored_items"])
            with pytest.raises(Exception, match="REPAIR_CONTENT_CURRENT_VERSION"):
                await repair_missing_current_versions(db, dry_run=False, limit=2, confirm="WRONG")

        async with AsyncSessionLocal() as db:
            result = await repair_missing_current_versions(
                db,
                dry_run=False,
                limit=2,
                confirm="REPAIR_CONTENT_CURRENT_VERSION",
            )
            package = await db.get(ContentPackage, repair_package_id)
            assert result["changed"] >= 1
            assert package is not None
            assert package.current_version_id is not None
    finally:
        async with AsyncSessionLocal() as db:
            if repair_package_id:
                await db.execute(delete(ContentPackageVersion).where(ContentPackageVersion.package_id == repair_package_id))
                await db.execute(delete(ContentPackage).where(ContentPackage.id == repair_package_id))
            if ignored_package_id:
                await db.execute(delete(ContentPackage).where(ContentPackage.id == ignored_package_id))
            if "file_id" in locals() and file_id:
                await db.execute(delete(File).where(File.id == file_id))
            await db.commit()
