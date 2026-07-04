"""desktop-tools delete_file lifecycle integration coverage."""

import importlib.util
import json
import sys
import uuid
from pathlib import Path

import app.main  # noqa: F401 - registers content lifecycle event handlers
import pytest
from app.database import AsyncSessionLocal
from app.models.content import ContentPackage, ContentPackageVersion
from app.models.file import File
from app.models.recycle import RecycleItem
from app.models.user import User
from sqlalchemy import delete, select

REPO_ROOT = Path(__file__).resolve().parents[2]
DESKTOP_TOOLS_BACKEND = REPO_ROOT / "modules" / "desktop-tools" / "backend"
sys.path.insert(0, str(DESKTOP_TOOLS_BACKEND))
spec = importlib.util.spec_from_file_location(
    "desktop_tools_router_under_test",
    DESKTOP_TOOLS_BACKEND / "router.py",
)
assert spec is not None and spec.loader is not None
desktop_tools_router = importlib.util.module_from_spec(spec)
spec.loader.exec_module(desktop_tools_router)


async def _cleanup(user_id: int | None, file_id: int | None, package_id: int | None) -> None:
    async with AsyncSessionLocal() as db:
        if package_id:
            await db.execute(delete(ContentPackageVersion).where(ContentPackageVersion.package_id == package_id))
            await db.execute(delete(ContentPackage).where(ContentPackage.id == package_id))
        if file_id:
            await db.execute(delete(RecycleItem).where(RecycleItem.origin_id == file_id))
            await db.execute(delete(File).where(File.id == file_id))
        if user_id:
            await db.execute(delete(User).where(User.id == user_id))
        await db.commit()


@pytest.mark.asyncio
async def test_desktop_tools_delete_file_emits_lifecycle_and_archives_content_package() -> None:
    user_id = None
    file_id = None
    package_id = None
    async with AsyncSessionLocal() as db:
        user = User(
            username=f"desktop-life-{uuid.uuid4().hex}",
            password_hash="test",
            display_name="Desktop Lifecycle Test",
            role="editor",
            enabled=True,
        )
        db.add(user)
        await db.flush()
        file = File(
            name=f"desktop-life-{uuid.uuid4().hex}",
            extension="txt",
            size=1,
            owner_id=user.id,
            storage_path=f"desktop-life-{uuid.uuid4().hex}.txt",
            mime_type="text/plain",
            md5_hash=uuid.uuid4().hex,
            deleted=False,
        )
        db.add(file)
        await db.flush()
        package = ContentPackage(
            owner_id=user.id,
            source_file_id=file.id,
            package_type="text",
            origin_type="generated",
            source_extension="txt",
            status="parsed",
        )
        db.add(package)
        await db.flush()
        user_id = user.id
        file_id = file.id
        package_id = package.id
        await db.commit()

    try:
        result = await desktop_tools_router._delete_file({"file_id": file_id}, f"user:{user_id}")
        assert result == {"file_id": file_id, "deleted": True}

        async with AsyncSessionLocal() as db:
            file = await db.get(File, file_id)
            package = await db.get(ContentPackage, package_id)
            recycle_item = await db.scalar(
                select(RecycleItem).where(
                    RecycleItem.origin_id == file_id,
                    RecycleItem.item_type == "file",
                    RecycleItem.owner_id == user_id,
                )
            )
            assert file is not None and file.deleted is True
            assert recycle_item is not None
            assert package is not None
            assert package.status == "archived"
            assert package.parse_error == "source_file_deleted"
            manifest = json.loads(package.manifest_json or "{}")
            assert manifest["lifecycle"]["archived_by_lifecycle"] is True
    finally:
        await _cleanup(user_id, file_id, package_id)
