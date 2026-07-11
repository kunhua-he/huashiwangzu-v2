from uuid import uuid4

import pytest
from app.database import AsyncSessionLocal
from sqlalchemy import text

from modules.knowledge.backend.services.lifecycle_debt_service import audit_lifecycle_debt


async def _cleanup(marker: str) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(
            text("DELETE FROM kb_documents WHERE filename LIKE :marker"),
            {"marker": f"%{marker}%"},
        )
        await db.commit()


@pytest.mark.asyncio
async def test_lifecycle_debt_all_owners_matches_gate_scope() -> None:
    marker = uuid4().hex
    await _cleanup(marker)
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(
                text(
                    """
                    INSERT INTO kb_documents
                        (owner_id, file_id, filename, extension, file_size, mime_type,
                         parse_status, vector_status, raw_status, fusion_status,
                         total_chunks, total_pages, deleted, created_at, updated_at)
                    VALUES
                        (1, 990000001, :owner_one, 'txt', 1, 'text/plain',
                         'pending', 'pending', 'pending', 'pending', 0, 0, false, now(), now()),
                        (2, 990000002, :owner_two, 'txt', 1, 'text/plain',
                         'pending', 'pending', 'pending', 'pending', 0, 0, false, now(), now())
                    """
                ),
                {
                    "owner_one": f"lifecycle-owner-one-{marker}.txt",
                    "owner_two": f"lifecycle-owner-two-{marker}.txt",
                },
            )
            await db.commit()

        async with AsyncSessionLocal() as db:
            owner_one = await audit_lifecycle_debt(db, 1, limit=5000, reason="source_file_missing")
            all_owners = await audit_lifecycle_debt(db, None, limit=5000, reason="source_file_missing")

        owner_one_ids = {
            item["document_id"]
            for item in owner_one["items"]
            if marker in item["filename"]
        }
        all_owner_items = [
            item
            for item in all_owners["items"]
            if marker in item["filename"]
        ]

        assert len(owner_one_ids) == 1
        assert len(all_owner_items) == 2
        assert {item["owner_id"] for item in all_owner_items} == {1, 2}
        assert all_owners["owner_scope"] == "all"
    finally:
        await _cleanup(marker)
