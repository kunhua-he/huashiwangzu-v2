"""Recycle permanent-delete lifecycle event coverage."""

import uuid

import pytest
from app.database import AsyncSessionLocal
from app.models.file import File, Folder
from app.models.recycle import RecycleItem
from app.models.user import User
from app.routers import files as files_router
from app.routers import recycle as recycle_router
from app.schemas.file import DeleteRequest
from app.schemas.recycle import RestoreRequest
from sqlalchemy import delete, select


async def _create_user(db, role: str = "admin") -> User:
    user = User(
        username=f"recycle-life-{uuid.uuid4().hex}",
        password_hash="test",
        display_name="Recycle Lifecycle Test",
        role=role,
        enabled=True,
    )
    db.add(user)
    await db.flush()
    return user


async def _create_deleted_file(db, owner_id: int, *, folder_id: int | None = None) -> File:
    file = File(
        name=f"recycle-life-{uuid.uuid4().hex}",
        extension="txt",
        size=1,
        folder_id=folder_id,
        owner_id=owner_id,
        storage_path=f"recycle-life-{uuid.uuid4().hex}.txt",
        mime_type="text/plain",
        md5_hash=uuid.uuid4().hex,
        deleted=True,
    )
    db.add(file)
    await db.flush()
    return file


async def _create_active_file(db, owner_id: int, *, folder_id: int | None = None) -> File:
    file = File(
        name=f"file-life-{uuid.uuid4().hex}",
        extension="txt",
        size=1,
        folder_id=folder_id,
        owner_id=owner_id,
        storage_path=f"file-life-{uuid.uuid4().hex}.txt",
        mime_type="text/plain",
        md5_hash=uuid.uuid4().hex,
        deleted=False,
    )
    db.add(file)
    await db.flush()
    return file


@pytest.mark.asyncio
async def test_delete_and_restore_folder_emit_child_file_lifecycle_events(monkeypatch) -> None:
    deleted_events: list[int] = []
    restored_events: list[int] = []

    async def fake_file_emit(event_name: str, file_id: int, user: User) -> None:
        assert event_name == "file.deleted"
        deleted_events.append(file_id)

    async def fake_recycle_emit(event_name: str, file_id: int, user: User) -> None:
        assert event_name == "file.restored"
        restored_events.append(file_id)

    monkeypatch.setattr(files_router, "_emit_file_event", fake_file_emit)
    monkeypatch.setattr(recycle_router, "_emit_file_event", fake_recycle_emit)
    user_id = None
    async with AsyncSessionLocal() as db:
        user = await _create_user(db, role="editor")
        user_id = user.id
        folder = Folder(name=f"soft-folder-{uuid.uuid4().hex}", owner_id=user.id, deleted=False)
        db.add(folder)
        await db.flush()
        child_file = await _create_active_file(db, user.id, folder_id=folder.id)
        child_folder = Folder(
            name=f"soft-subfolder-{uuid.uuid4().hex}",
            owner_id=user.id,
            parent_id=folder.id,
            deleted=False,
        )
        db.add(child_folder)
        await db.flush()
        nested_file = await _create_active_file(db, user.id, folder_id=child_folder.id)
        await db.commit()

        await files_router.delete_item(DeleteRequest(type="folder", id=folder.id), db, user)

        assert sorted(deleted_events) == sorted([child_file.id, nested_file.id])
        recycle = (await db.execute(
            select(RecycleItem).where(
                RecycleItem.origin_id == folder.id,
                RecycleItem.item_type == "folder",
                RecycleItem.owner_id == user.id,
            )
        )).scalar_one()

        await recycle_router.restore(RestoreRequest(item_type="folder", id=recycle.id), db, user)

        assert sorted(restored_events) == sorted([child_file.id, nested_file.id])

    async with AsyncSessionLocal() as db:
        if user_id:
            await db.execute(delete(RecycleItem).where(RecycleItem.owner_id == user_id))
            await db.execute(delete(File).where(File.owner_id == user_id))
            await db.execute(delete(Folder).where(Folder.owner_id == user_id))
            await db.execute(delete(User).where(User.id == user_id))
            await db.commit()


@pytest.mark.asyncio
async def test_permanent_delete_single_file_emits_exactly_one_event(monkeypatch) -> None:
    emitted: list[int] = []

    async def fake_emit(event_name: str, file_id: int, user: User) -> None:
        assert event_name == "file.permanent_deleted"
        emitted.append(file_id)

    monkeypatch.setattr(recycle_router, "_emit_file_event", fake_emit)
    user_id = None
    async with AsyncSessionLocal() as db:
        user = await _create_user(db, role="editor")
        user_id = user.id
        file = await _create_deleted_file(db, user.id)
        recycle = RecycleItem(origin_id=file.id, item_type="file", name=file.name, owner_id=user.id)
        db.add(recycle)
        await db.commit()

        result = await recycle_router.delete_permanently(
            RestoreRequest(item_type="file", id=recycle.id),
            db,
            user,
        )

        assert emitted == [file.id]
        assert result.data["permanently_deleted_file_ids"] == [file.id]

    async with AsyncSessionLocal() as db:
        if user_id:
            await db.execute(delete(User).where(User.id == user_id))
            await db.commit()


@pytest.mark.asyncio
async def test_permanent_delete_folder_emits_all_child_file_ids(monkeypatch) -> None:
    emitted: list[int] = []

    async def fake_emit(event_name: str, file_id: int, user: User) -> None:
        assert event_name == "file.permanent_deleted"
        emitted.append(file_id)

    monkeypatch.setattr(recycle_router, "_emit_file_event", fake_emit)
    user_id = None
    async with AsyncSessionLocal() as db:
        user = await _create_user(db, role="editor")
        user_id = user.id
        folder = Folder(name=f"recycle-folder-{uuid.uuid4().hex}", owner_id=user.id, deleted=True)
        db.add(folder)
        await db.flush()
        child_file = await _create_deleted_file(db, user.id, folder_id=folder.id)
        child_folder = Folder(
            name=f"recycle-subfolder-{uuid.uuid4().hex}",
            owner_id=user.id,
            parent_id=folder.id,
            deleted=True,
        )
        db.add(child_folder)
        await db.flush()
        nested_file = await _create_deleted_file(db, user.id, folder_id=child_folder.id)
        recycle = RecycleItem(origin_id=folder.id, item_type="folder", name=folder.name, owner_id=user.id)
        db.add(recycle)
        await db.commit()

        result = await recycle_router.delete_permanently(
            RestoreRequest(item_type="folder", id=recycle.id),
            db,
            user,
        )

        assert sorted(emitted) == sorted([child_file.id, nested_file.id])
        assert sorted(result.data["permanently_deleted_file_ids"]) == sorted([child_file.id, nested_file.id])

    async with AsyncSessionLocal() as db:
        if user_id:
            await db.execute(delete(User).where(User.id == user_id))
            await db.commit()


@pytest.mark.asyncio
async def test_permanent_delete_folder_ignores_cross_owner_child_rows(monkeypatch) -> None:
    emitted: list[int] = []

    async def fake_emit(event_name: str, file_id: int, user: User) -> None:
        assert event_name == "file.permanent_deleted"
        emitted.append(file_id)

    monkeypatch.setattr(recycle_router, "_emit_file_event", fake_emit)
    owner_id = None
    other_id = None
    cross_owner_file_id = None
    async with AsyncSessionLocal() as db:
        owner = await _create_user(db, role="editor")
        other = await _create_user(db, role="editor")
        owner_id = owner.id
        other_id = other.id
        folder = Folder(name=f"owner-folder-{uuid.uuid4().hex}", owner_id=owner.id, deleted=True)
        db.add(folder)
        await db.flush()
        cross_owner_file = await _create_deleted_file(db, other.id, folder_id=folder.id)
        cross_owner_file_id = cross_owner_file.id
        recycle = RecycleItem(origin_id=folder.id, item_type="folder", name=folder.name, owner_id=owner.id)
        db.add(recycle)
        await db.commit()

        result = await recycle_router.delete_permanently(
            RestoreRequest(item_type="folder", id=recycle.id),
            db,
            owner,
        )

        assert emitted == []
        assert result.data["permanently_deleted_file_ids"] == []
        remaining = await db.get(File, cross_owner_file_id)
        assert remaining is not None
        assert remaining.owner_id == other.id

    async with AsyncSessionLocal() as db:
        if cross_owner_file_id:
            await db.execute(delete(File).where(File.id == cross_owner_file_id))
        if owner_id or other_id:
            await db.execute(delete(User).where(User.id.in_([value for value in [owner_id, other_id] if value])))
        await db.commit()


@pytest.mark.asyncio
async def test_empty_trash_emits_top_level_and_folder_child_file_ids(monkeypatch) -> None:
    emitted: list[int] = []

    async def fake_emit(event_name: str, file_id: int, user: User) -> None:
        assert event_name == "file.permanent_deleted"
        emitted.append(file_id)

    monkeypatch.setattr(recycle_router, "_emit_file_event", fake_emit)
    user_id = None
    async with AsyncSessionLocal() as db:
        user = await _create_user(db, role="admin")
        user_id = user.id
        top_file = await _create_deleted_file(db, user.id)
        folder = Folder(name=f"empty-folder-{uuid.uuid4().hex}", owner_id=user.id, deleted=True)
        db.add(folder)
        await db.flush()
        child_file = await _create_deleted_file(db, user.id, folder_id=folder.id)
        db.add_all([
            RecycleItem(origin_id=top_file.id, item_type="file", name=top_file.name, owner_id=user.id),
            RecycleItem(origin_id=folder.id, item_type="folder", name=folder.name, owner_id=user.id),
        ])
        await db.commit()

        result = await recycle_router.empty_trash(db, user)

        assert sorted(emitted) == sorted([top_file.id, child_file.id])
        assert sorted(result.data["permanently_deleted_file_ids"]) == sorted([top_file.id, child_file.id])

    async with AsyncSessionLocal() as db:
        if user_id:
            await db.execute(delete(User).where(User.id == user_id))
            await db.commit()
