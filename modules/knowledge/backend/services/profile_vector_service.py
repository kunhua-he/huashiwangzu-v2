"""Profile vector sidecar helpers for relation candidate recall."""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import KbDocumentProfile
from .analysis_artifact_service import stable_hash

logger = logging.getLogger("v2.knowledge").getChild("profile_vector")

PROFILE_VECTOR_DIM = 1024
PROFILE_VECTOR_MODEL = "bge-m3"


def normalize_profile_embedding(value: Any) -> list[float]:
    if not isinstance(value, list) or len(value) != PROFILE_VECTOR_DIM:
        return []
    try:
        return [float(item) for item in value]
    except (TypeError, ValueError):
        return []


def vector_literal(embedding: list[float]) -> str:
    return "[" + ",".join(f"{float(item):.8g}" for item in embedding) + "]"


def profile_vector_source_hash(embedding: list[float]) -> str:
    return stable_hash({
        "model": PROFILE_VECTOR_MODEL,
        "dim": len(embedding),
        "embedding_head": [round(float(item), 8) for item in embedding[:16]],
        "embedding_tail": [round(float(item), 8) for item in embedding[-16:]],
    })


async def upsert_profile_vector(
    db: AsyncSession,
    *,
    owner_id: int,
    document_id: int,
    profile_id: int | None,
    embedding: list[float],
) -> bool:
    normalized = normalize_profile_embedding(embedding)
    if not normalized:
        return False
    await db.execute(
        text(
            """
            INSERT INTO kb_document_profile_vectors (
                owner_id, document_id, profile_id, embedding,
                embedding_model, source_hash, status
            )
            VALUES (
                :owner_id, :document_id, :profile_id, CAST(:embedding AS vector),
                :embedding_model, :source_hash, 'active'
            )
            ON CONFLICT (owner_id, document_id)
            DO UPDATE SET
                profile_id = EXCLUDED.profile_id,
                embedding = EXCLUDED.embedding,
                embedding_model = EXCLUDED.embedding_model,
                source_hash = EXCLUDED.source_hash,
                status = 'active',
                updated_at = now()
            """
        ),
        {
            "owner_id": owner_id,
            "document_id": document_id,
            "profile_id": profile_id,
            "embedding": vector_literal(normalized),
            "embedding_model": PROFILE_VECTOR_MODEL,
            "source_hash": profile_vector_source_hash(normalized),
        },
    )
    return True


async def ensure_document_profile_vector(
    db: AsyncSession,
    *,
    owner_id: int,
    document_id: int,
) -> list[float]:
    result = await db.execute(
        select(KbDocumentProfile.id, KbDocumentProfile.profile_embedding)
        .where(
            KbDocumentProfile.owner_id == owner_id,
            KbDocumentProfile.document_id == document_id,
        )
        .order_by(KbDocumentProfile.id.desc())
        .limit(1)
    )
    row = result.first()
    embedding = normalize_profile_embedding(row[1] if row else None)
    if not embedding:
        return []
    await upsert_profile_vector(
        db,
        owner_id=owner_id,
        document_id=document_id,
        profile_id=int(row[0]) if row and row[0] is not None else None,
        embedding=embedding,
    )
    return embedding


async def backfill_profile_vectors(
    db: AsyncSession,
    *,
    owner_id: int | None = None,
    limit: int = 5000,
) -> dict:
    stmt = (
        select(
            KbDocumentProfile.id,
            KbDocumentProfile.owner_id,
            KbDocumentProfile.document_id,
            KbDocumentProfile.profile_embedding,
        )
        .where(KbDocumentProfile.profile_embedding.isnot(None))
        .order_by(KbDocumentProfile.id)
        .limit(limit)
    )
    if owner_id is not None:
        stmt = stmt.where(KbDocumentProfile.owner_id == owner_id)
    result = await db.execute(stmt)
    scanned = 0
    upserted = 0
    skipped = 0
    for profile_id, row_owner_id, document_id, profile_embedding in result.all():
        scanned += 1
        embedding = normalize_profile_embedding(profile_embedding)
        if not embedding:
            skipped += 1
            continue
        if await upsert_profile_vector(
            db,
            owner_id=int(row_owner_id),
            document_id=int(document_id),
            profile_id=int(profile_id),
            embedding=embedding,
        ):
            upserted += 1
    await db.commit()
    logger.info("Backfilled profile vectors scanned=%d upserted=%d skipped=%d", scanned, upserted, skipped)
    return {"scanned": scanned, "upserted": upserted, "skipped": skipped}
