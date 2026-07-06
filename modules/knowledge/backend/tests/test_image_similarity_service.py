"""Tests for knowledge image fingerprinting and similarity grouping."""
from __future__ import annotations

import io
import os
import sys
import uuid
from pathlib import Path

import pytest
from PIL import Image, ImageDraw
from sqlalchemy import delete as sa_delete
from sqlalchemy import func, or_, select, text

os.environ.setdefault("JWT_SECRET", "test-secret-for-knowledge-image-similarity")

REPO_ROOT = Path(__file__).resolve().parents[4]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.database import AsyncSessionLocal

from modules.knowledge.backend.init_db import ensure_kb_indexes, ensure_kb_tables
from modules.knowledge.backend.models import (
    KbDocument,
    KbImageAsset,
    KbImageSimilarityGroup,
    KbImageSimilarPair,
    KbRawData,
)
from modules.knowledge.backend.services.image_similarity_service import (
    classify_similarity,
    compute_image_fingerprints,
    hamming_distance,
    record_document_image_assets,
)

OWNER_ID = 910_000_100
TEST_FILE_IDS = (910_000_101, 910_000_102)


def _png_bytes(label: str, accent: tuple[int, int, int]) -> bytes:
    image = Image.new("RGB", (160, 120), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((16, 12, 144, 104), outline=accent, width=6)
    draw.rectangle((42, 36, 118, 76), fill=(245, 245, 245), outline=(40, 40, 40), width=2)
    draw.text((50, 48), label, fill=(20, 20, 20))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


async def _ensure_schema() -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await db.commit()
        await ensure_kb_tables(db)
        await ensure_kb_indexes(db)
        await _cleanup_stale_rows(db)


async def _delete_document_rows(db, document_id: int) -> None:
    asset_ids = [
        int(asset_id)
        for asset_id in (
            await db.execute(select(KbImageAsset.id).where(KbImageAsset.document_id == document_id))
        ).scalars().all()
    ]
    if asset_ids:
        await db.execute(
            sa_delete(KbImageSimilarPair).where(
                or_(
                    KbImageSimilarPair.source_asset_id.in_(asset_ids),
                    KbImageSimilarPair.target_asset_id.in_(asset_ids),
                )
            )
        )
    await db.execute(text("DELETE FROM kb_image_assets WHERE document_id = :document_id"), {"document_id": document_id})
    await db.execute(text("DELETE FROM kb_raw_data WHERE document_id = :document_id"), {"document_id": document_id})
    await db.execute(text("DELETE FROM kb_documents WHERE id = :document_id"), {"document_id": document_id})


async def _cleanup_stale_rows(db) -> None:
    result = await db.execute(
        select(KbDocument.id).where(
            or_(
                KbDocument.file_id.in_(TEST_FILE_IDS),
                KbDocument.filename.like("image-sim-%"),
            )
        )
    )
    for document_id in result.scalars().all():
        await _delete_document_rows(db, int(document_id))
    await db.execute(text("DELETE FROM kb_image_similarity_groups WHERE owner_id = :owner_id"), {"owner_id": OWNER_ID})
    await db.commit()


async def _cleanup(document_ids: list[int]) -> None:
    async with AsyncSessionLocal() as db:
        for document_id in document_ids:
            await _delete_document_rows(db, document_id)
        await db.execute(text("DELETE FROM kb_image_similarity_groups WHERE owner_id = :owner_id"), {"owner_id": OWNER_ID})
        await db.commit()


def test_image_hashing_and_similarity_thresholds() -> None:
    first = _png_bytes("A", (180, 40, 40))
    second = _png_bytes("A", (180, 42, 42))

    first_hashes = compute_image_fingerprints(first)
    second_hashes = compute_image_fingerprints(second)
    phash_distance = hamming_distance(first_hashes.phash, second_hashes.phash)
    dhash_distance = hamming_distance(first_hashes.dhash, second_hashes.dhash)

    assert first_hashes.file_md5 != second_hashes.file_md5
    assert phash_distance is not None
    assert dhash_distance is not None
    level, reason = classify_similarity(
        hamming_phash=phash_distance,
        hamming_dhash=dhash_distance,
        text_similarity=1.0,
    )
    assert level == "high"
    assert reason


@pytest.mark.asyncio
async def test_record_document_image_assets_creates_pair_and_group() -> None:
    marker = uuid.uuid4().hex[:8]
    document_ids: list[int] = []
    await _ensure_schema()
    try:
        async with AsyncSessionLocal() as db:
            doc_one = KbDocument(
                owner_id=OWNER_ID,
                file_id=TEST_FILE_IDS[0],
                filename=f"image-sim-{marker}-one.png",
                extension="png",
                file_size=100,
                mime_type="image/png",
                parse_status="done",
                raw_status="done",
                total_pages=1,
                deleted=False,
            )
            doc_two = KbDocument(
                owner_id=OWNER_ID,
                file_id=TEST_FILE_IDS[1],
                filename=f"image-sim-{marker}-two.png",
                extension="png",
                file_size=100,
                mime_type="image/png",
                parse_status="done",
                raw_status="done",
                total_pages=1,
                deleted=False,
            )
            db.add_all([doc_one, doc_two])
            await db.flush()
            document_ids = [int(doc_one.id), int(doc_two.id)]
            db.add_all([
                KbRawData(
                    document_id=int(doc_one.id),
                    file_id=doc_one.file_id,
                    owner_id=OWNER_ID,
                    page=1,
                    round=2,
                    source_type="ocr",
                    content=f"same poster text {marker}",
                    status="done",
                ),
                KbRawData(
                    document_id=int(doc_two.id),
                    file_id=doc_two.file_id,
                    owner_id=OWNER_ID,
                    page=1,
                    round=2,
                    source_type="ocr",
                    content=f"same poster text {marker}",
                    status="done",
                ),
            ])
            await db.commit()

        async with AsyncSessionLocal() as db:
            first_result = await record_document_image_assets(
                db,
                owner_id=OWNER_ID,
                document_id=document_ids[0],
                file_id=TEST_FILE_IDS[0],
                page_images={1: _png_bytes("A", (180, 40, 40))},
                asset_type="image_file",
            )
            second_result = await record_document_image_assets(
                db,
                owner_id=OWNER_ID,
                document_id=document_ids[1],
                file_id=TEST_FILE_IDS[1],
                page_images={1: _png_bytes("A", (180, 42, 42))},
                asset_type="image_file",
            )
            rerun_result = await record_document_image_assets(
                db,
                owner_id=OWNER_ID,
                document_id=document_ids[1],
                file_id=TEST_FILE_IDS[1],
                page_images={1: _png_bytes("A", (180, 42, 42))},
                asset_type="image_file",
            )

        async with AsyncSessionLocal() as db:
            asset_count = await db.scalar(
                select(func.count(KbImageAsset.id)).where(KbImageAsset.owner_id == OWNER_ID)
            )
            pair_count = await db.scalar(
                select(func.count(KbImageSimilarPair.id)).where(KbImageSimilarPair.owner_id == OWNER_ID)
            )
            pair = await db.scalar(
                select(KbImageSimilarPair).where(KbImageSimilarPair.owner_id == OWNER_ID)
            )
            group_count = await db.scalar(
                select(func.count(KbImageSimilarityGroup.id)).where(KbImageSimilarityGroup.owner_id == OWNER_ID)
            )

        assert first_result["assets"] == 1
        assert second_result["assets"] == 1
        assert rerun_result["assets"] == 1
        assert second_result["high"] >= 1
        assert asset_count == 2
        assert pair_count == 1
        assert pair is not None
        assert pair.similarity_level == "high"
        assert pair.hamming_phash is not None
        assert pair.hamming_dhash is not None
        assert group_count == 1
    finally:
        await _cleanup(document_ids)
