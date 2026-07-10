import hashlib
from pathlib import Path
from uuid import uuid4

import pytest
from app.config import get_settings
from app.database import AsyncSessionLocal, init_db
from app.models.file import File
from app.models.file_share import FileShare
from app.models.user import User
from app.services.auth import hash_password
from sqlalchemy import delete

from modules.knowledge.backend.models import KbChunk, KbDocument
from modules.knowledge.backend.services.document_service import get_document, list_documents
from modules.knowledge.backend.services.embedding_service import get_chunk_by_id
from modules.knowledge.backend.services.progress_service import get_document_progress
from modules.knowledge.backend.services.search_service import get_document_chunks


@pytest.mark.asyncio
async def test_shared_file_document_is_readable_by_receiver() -> None:
    await init_db()
    marker = uuid4().hex
    owner_id = 990101
    viewer_id = 990102
    content = f"shared knowledge {marker}".encode()
    md5_hash = hashlib.md5(content).hexdigest()
    storage_path = f"test-shared-knowledge/{marker}.txt"
    upload_path = Path(get_settings().UPLOAD_DIR) / storage_path
    upload_path.parent.mkdir(parents=True, exist_ok=True)
    upload_path.write_bytes(content)

    file_id = 0
    doc_id = 0
    chunk_id = 0
    try:
        async with AsyncSessionLocal() as db:
            for user_id, username in ((owner_id, f"owner-{marker}"), (viewer_id, f"viewer-{marker}")):
                db.add(
                    User(
                        id=user_id,
                        username=username,
                        password_hash=hash_password("test-password"),
                        display_name=username,
                        role="viewer",
                        enabled=True,
                    )
                )
            await db.flush()

            file = File(
                name=f"shared-{marker}",
                extension="txt",
                size=len(content),
                folder_id=None,
                owner_id=owner_id,
                storage_path=storage_path,
                mime_type="text/plain",
                md5_hash=md5_hash,
                ref_count=1,
                deleted=False,
            )
            db.add(file)
            await db.flush()
            file_id = int(file.id)

            doc = KbDocument(
                owner_id=owner_id,
                file_id=file_id,
                filename=f"shared-{marker}.txt",
                extension="txt",
                file_size=len(content),
                mime_type="text/plain",
                parse_status="done",
                vector_status="done",
                raw_status="done",
                fusion_status="done",
                total_chunks=1,
                total_pages=1,
            )
            db.add(doc)
            await db.flush()
            doc_id = int(doc.id)

            chunk = KbChunk(
                document_id=doc_id,
                owner_id=owner_id,
                page=1,
                chunk_index=0,
                block_type="段落",
                text=f"shared text {marker}",
                keywords=marker,
            )
            db.add(chunk)
            await db.flush()
            chunk_id = int(chunk.id)

            db.add(
                FileShare(
                    file_id=file_id,
                    shared_by_owner_id=owner_id,
                    shared_with_user_id=viewer_id,
                    permission="read",
                )
            )
            await db.commit()

        async with AsyncSessionLocal() as db:
            listed = await list_documents(db, viewer_id, page_size=100)
            assert any(int(item["id"]) == doc_id for item in listed["items"])
            detail = await get_document(db, doc_id, viewer_id)
            assert int(detail["owner_id"]) == owner_id
            progress = await get_document_progress(db, doc_id, viewer_id)
            assert progress["document_id"] == doc_id
            chunks = await get_document_chunks(db, doc_id, owner_id=viewer_id)
            assert [int(chunk["id"]) for chunk in chunks] == [chunk_id]
            chunk_detail = await get_chunk_by_id(db, chunk_id, owner_id=viewer_id)
            assert chunk_detail and int(chunk_detail["document_id"]) == doc_id
    finally:
        async with AsyncSessionLocal() as db:
            if file_id:
                await db.execute(delete(FileShare).where(FileShare.file_id == file_id))
            if chunk_id:
                await db.execute(delete(KbChunk).where(KbChunk.id == chunk_id))
            if doc_id:
                await db.execute(delete(KbDocument).where(KbDocument.id == doc_id))
            if file_id:
                await db.execute(delete(File).where(File.id == file_id))
            await db.execute(delete(User).where(User.id.in_([owner_id, viewer_id])))
            await db.commit()
        try:
            upload_path.unlink()
        except FileNotFoundError:
            pass
