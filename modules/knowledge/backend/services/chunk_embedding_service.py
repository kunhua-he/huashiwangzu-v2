"""Versioned chunk embedding sidecar helpers."""
from __future__ import annotations

import json
import logging
from contextlib import nullcontext
from typing import Any

from app.database import AsyncSessionLocal
from app.gateway.config import get_model_type_config
from app.models.file import File
from app.models.system import SystemTaskQueue
from app.services.model_services import get_embedding_profile_contract, get_embeddings
from app.services.model_watchdog.watchdog import use_model
from app.services.task_dispatcher import publish_task
from app.services.task_worker import register_task_handler
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import KbChunk, KbDocument
from .analysis_artifact_service import stable_hash
from .profile_vector_service import vector_literal

logger = logging.getLogger("v2.knowledge").getChild("chunk_embedding")

DEFAULT_CHUNK_EMBEDDING_PROFILE = "qwen3-embedding-8b"
DEFAULT_CHUNK_EMBEDDING_DIM = 4096
DEFAULT_CHUNK_EMBEDDING_VERSION = 1
DEFAULT_CHUNK_EMBEDDING_BATCH_SIZE = 8
CHUNK_EMBEDDING_BACKFILL_TASK_TYPE = "kb_chunk_embedding_backfill"
DEFAULT_CHUNK_EMBEDDING_TASK_LIMIT = 600000
DEFAULT_CHUNK_EMBEDDING_TASK_CHUNK_LIMIT = 96
DEFAULT_CHUNK_EMBEDDING_TASK_BATCH_SIZE = 4


def resolve_chunk_embedding_contract(profile_key: str | None = None) -> dict[str, Any]:
    embedding_config = get_model_type_config("embedding")
    configured_default = str(
        embedding_config.get("knowledge_sidecar_primary") or DEFAULT_CHUNK_EMBEDDING_PROFILE
    )
    profile = get_embedding_profile_contract(profile_key or configured_default)
    dimensions = int(profile.get("dimensions") or profile.get("embedding_dim") or DEFAULT_CHUNK_EMBEDDING_DIM)
    if dimensions <= 0:
        raise ValueError(f"Invalid embedding dimensions for profile {profile.get('profile_key')}: {dimensions}")
    version = int(profile.get("embedding_version") or DEFAULT_CHUNK_EMBEDDING_VERSION)
    vector_store = str(profile.get("vector_store") or "kb_chunk_embeddings")
    model_key = str(profile.get("profile_key") or profile_key or DEFAULT_CHUNK_EMBEDDING_PROFILE)
    return {
        "profile_key": model_key,
        "embedding_model": model_key,
        "dimensions": dimensions,
        "embedding_version": version,
        "vector_store": vector_store,
        "vector_index": profile.get("vector_index"),
        "index_dimensions": int(profile.get("index_dimensions") or min(dimensions, 2000)),
        "index_strategy": profile.get("index_strategy"),
        "rerank_full_vector": bool(profile.get("rerank_full_vector", dimensions > 2000)),
        "model": profile.get("model"),
        "provider": profile.get("provider"),
        "watchdog": profile.get("watchdog"),
    }


def chunk_embedding_source_hash(*, text_value: str, contract: dict[str, Any]) -> str:
    return stable_hash({
        "profile_key": contract["profile_key"],
        "embedding_model": contract["embedding_model"],
        "embedding_version": contract["embedding_version"],
        "dimensions": contract["dimensions"],
        "text": text_value or "",
    })


def normalize_chunk_embedding(embedding: Any, *, dimensions: int) -> list[float]:
    if not isinstance(embedding, list) or len(embedding) != dimensions:
        return []
    try:
        return [float(item) for item in embedding]
    except (TypeError, ValueError):
        return []


async def upsert_chunk_embedding(
    db: AsyncSession,
    *,
    chunk: KbChunk,
    embedding: list[float],
    contract: dict[str, Any],
) -> bool:
    dimensions = int(contract["dimensions"])
    normalized = normalize_chunk_embedding(embedding, dimensions=dimensions)
    if not normalized:
        return False
    source_hash = chunk_embedding_source_hash(text_value=chunk.text or "", contract=contract)
    await db.execute(
        text(
            """
            INSERT INTO kb_chunk_embeddings (
                owner_id, document_id, chunk_id, index_layer,
                embedding_model, embedding_version, embedding_dim,
                embedding, source_hash, status, diagnostics_json
            )
            VALUES (
                :owner_id, :document_id, :chunk_id, :index_layer,
                :embedding_model, :embedding_version, :embedding_dim,
                CAST(:embedding AS vector), :source_hash, 'active', CAST(:diagnostics_json AS json)
            )
            ON CONFLICT (owner_id, chunk_id, embedding_model, embedding_version)
            DO UPDATE SET
                document_id = EXCLUDED.document_id,
                index_layer = EXCLUDED.index_layer,
                embedding_dim = EXCLUDED.embedding_dim,
                embedding = EXCLUDED.embedding,
                source_hash = EXCLUDED.source_hash,
                status = 'active',
                diagnostics_json = EXCLUDED.diagnostics_json,
                updated_at = now()
            """
        ),
        {
            "owner_id": chunk.owner_id,
            "document_id": chunk.document_id,
            "chunk_id": chunk.id,
            "index_layer": chunk.index_layer or "base_parse",
            "embedding_model": contract["embedding_model"],
            "embedding_version": contract["embedding_version"],
            "embedding_dim": dimensions,
            "embedding": vector_literal(normalized),
            "source_hash": source_hash,
            "diagnostics_json": json.dumps(
                {
                    "schema_version": "kb_chunk_embedding_v1",
                    "profile_key": contract["profile_key"],
                    "vector_store": contract["vector_store"],
                },
                ensure_ascii=False,
            ),
        },
    )
    return True


async def get_chunk_embedding_counts(
    db: AsyncSession,
    *,
    owner_id: int,
    profile_key: str | None = None,
) -> dict[str, Any]:
    contract = resolve_chunk_embedding_contract(profile_key)
    vector_store = str(contract["vector_store"])
    eligible_total = await db.scalar(
        select(func.count(KbChunk.id))
        .select_from(KbChunk)
        .join(KbDocument, KbDocument.id == KbChunk.document_id)
        .join(File, File.id == KbDocument.file_id)
        .where(
            KbChunk.owner_id == owner_id,
            KbDocument.owner_id == owner_id,
            KbDocument.deleted.is_(False),
            File.deleted.is_(False),
            KbChunk.text != "",
        )
    ) or 0
    if vector_store == "kb_chunks":
        active_total = await db.scalar(
            select(func.count(KbChunk.id))
            .select_from(KbChunk)
            .join(KbDocument, KbDocument.id == KbChunk.document_id)
            .join(File, File.id == KbDocument.file_id)
            .where(
                KbChunk.owner_id == owner_id,
                KbDocument.owner_id == owner_id,
                KbDocument.deleted.is_(False),
                File.deleted.is_(False),
                KbChunk.text != "",
                KbChunk.embedding.is_not(None),
            )
        ) or 0
    else:
        active_total = await db.scalar(
            text(
                """
                SELECT count(*)
                FROM kb_chunk_embeddings
                WHERE owner_id = :owner_id
                  AND embedding_model = :embedding_model
                  AND embedding_version = :embedding_version
                  AND embedding_dim = :embedding_dim
                  AND status = 'active'
                """
            ),
            {
                "owner_id": owner_id,
                "embedding_model": contract["embedding_model"],
                "embedding_version": contract["embedding_version"],
                "embedding_dim": contract["dimensions"],
            },
        ) or 0
    return {
        "profile_key": contract["profile_key"],
        "embedding_model": contract["embedding_model"],
        "embedding_version": contract["embedding_version"],
        "dimensions": contract["dimensions"],
        "vector_store": vector_store,
        "eligible_chunks": int(eligible_total),
        "active_embeddings": int(active_total),
        "remaining": max(0, int(eligible_total) - int(active_total)),
    }


def _chunk_embedding_dependency_key(owner_id: int, profile_key: str) -> str:
    return f"knowledge:chunk_embedding:{int(owner_id)}:{profile_key}"


async def enqueue_chunk_embedding_backfill_task(
    db: AsyncSession,
    *,
    owner_id: int,
    profile_key: str | None = None,
    total_limit: int = DEFAULT_CHUNK_EMBEDDING_TASK_LIMIT,
    chunk_limit: int = DEFAULT_CHUNK_EMBEDDING_TASK_CHUNK_LIMIT,
    batch_size: int = DEFAULT_CHUNK_EMBEDDING_TASK_BATCH_SIZE,
    priority: int = 4,
    embedded_total: int = 0,
    exclude_task_id: int | None = None,
) -> dict[str, Any]:
    contract = resolve_chunk_embedding_contract(profile_key)
    resolved_profile = str(contract["profile_key"])
    dependency_key = _chunk_embedding_dependency_key(owner_id, resolved_profile)
    filters = [
        SystemTaskQueue.module == "knowledge",
        SystemTaskQueue.task_type == CHUNK_EMBEDDING_BACKFILL_TASK_TYPE,
        SystemTaskQueue.status.in_(("pending", "running")),
        SystemTaskQueue.dependency_key == dependency_key,
    ]
    if exclude_task_id:
        filters.append(SystemTaskQueue.id != int(exclude_task_id))
    existing = await db.scalar(
        select(SystemTaskQueue)
        .where(*filters)
        .order_by(SystemTaskQueue.id.desc())
        .limit(1)
    )
    if existing:
        return {
            "enqueued": False,
            "task_id": int(existing.id),
            "reason": "chunk_embedding_backfill_already_in_flight",
            "profile_key": resolved_profile,
            "dependency_key": dependency_key,
        }

    payload = {
        "owner_id": int(owner_id),
        "embedding_profile": resolved_profile,
        "total_limit": max(1, min(int(total_limit or DEFAULT_CHUNK_EMBEDDING_TASK_LIMIT), 2_000_000)),
        "chunk_limit": max(1, min(int(chunk_limit or DEFAULT_CHUNK_EMBEDDING_TASK_CHUNK_LIMIT), 5000)),
        "batch_size": max(1, min(int(batch_size or DEFAULT_CHUNK_EMBEDDING_TASK_BATCH_SIZE), 64)),
        "priority": int(priority),
        "embedded_total": max(0, int(embedded_total or 0)),
    }
    task = await publish_task(
        db,
        task_type=CHUNK_EMBEDDING_BACKFILL_TASK_TYPE,
        module="knowledge",
        owner_id=int(owner_id),
        body=payload,
        requested_by=f"user:{int(owner_id)}",
        trigger="knowledge.chunk_embedding.backfill",
        priority=int(priority),
        max_retries=5,
        stage_key=resolved_profile,
        lane_key="derived_index",
        ready_status="ready",
        dependency_key=dependency_key,
    )
    return {
        "enqueued": True,
        "task_id": int(task.id),
        "reason": "chunk_embedding_backfill_created",
        "profile_key": resolved_profile,
        "dependency_key": dependency_key,
        "chunk_limit": payload["chunk_limit"],
        "batch_size": payload["batch_size"],
        "total_limit": payload["total_limit"],
    }


async def backfill_chunk_embeddings(
    db: AsyncSession,
    *,
    owner_id: int,
    profile_key: str | None = None,
    dry_run: bool = True,
    limit: int = 1000,
    batch_size: int = DEFAULT_CHUNK_EMBEDDING_BATCH_SIZE,
) -> dict[str, Any]:
    contract = resolve_chunk_embedding_contract(profile_key)
    dimensions = int(contract["dimensions"])
    limit = max(1, min(int(limit or 1000), 50000))
    batch_size = max(1, min(int(batch_size or DEFAULT_CHUNK_EMBEDDING_BATCH_SIZE), 64))

    stmt = (
        select(KbChunk)
        .join(KbDocument, KbDocument.id == KbChunk.document_id)
        .join(File, File.id == KbDocument.file_id)
        .where(
            KbChunk.owner_id == owner_id,
            KbDocument.owner_id == owner_id,
            KbDocument.deleted.is_(False),
            File.deleted.is_(False),
            KbChunk.text != "",
            text(
                """
                NOT EXISTS (
                    SELECT 1
                    FROM kb_chunk_embeddings e
                    WHERE e.owner_id = kb_chunks.owner_id
                      AND e.chunk_id = kb_chunks.id
                      AND e.embedding_model = :embedding_model
                      AND e.embedding_version = :embedding_version
                      AND e.embedding_dim = :embedding_dim
                      AND e.status = 'active'
                )
                """
            ),
        )
        .order_by(KbChunk.id)
        .limit(limit)
    )
    result = await db.execute(
        stmt,
        {
            "embedding_model": contract["embedding_model"],
            "embedding_version": contract["embedding_version"],
            "embedding_dim": dimensions,
        },
    )
    chunks = list(result.scalars().all())
    if dry_run:
        return {
            "dry_run": True,
            "profile_key": contract["profile_key"],
            "embedding_model": contract["embedding_model"],
            "embedding_version": contract["embedding_version"],
            "dimensions": dimensions,
            "vector_store": contract["vector_store"],
            "candidate_count": len(chunks),
            "sample_chunk_ids": [int(chunk.id) for chunk in chunks[:20]],
        }

    # Release the candidate-read transaction before the slow local embedding call.
    # The first Qwen3 request can spend minutes loading weights; keeping an
    # asyncpg transaction open during that window has caused stale connections.
    await db.commit()

    scanned = 0
    embedded = 0
    skipped = 0
    failed_batches = 0
    watchdog_name = str(contract.get("watchdog") or "").strip()
    usage_context = use_model(watchdog_name) if watchdog_name else nullcontext()
    with usage_context:
        for offset in range(0, len(chunks), batch_size):
            batch = chunks[offset:offset + batch_size]
            texts = [chunk.text or "" for chunk in batch]
            try:
                embeddings = await get_embeddings(texts, profile_key=contract["profile_key"])
            except Exception as exc:
                failed_batches += 1
                skipped += len(batch)
                logger.warning("Chunk embedding batch failed profile=%s offset=%d: %s", contract["profile_key"], offset, exc)
                continue
            for chunk, embedding in zip(batch, embeddings, strict=False):
                scanned += 1
                if await upsert_chunk_embedding(db, chunk=chunk, embedding=embedding, contract=contract):
                    embedded += 1
                else:
                    skipped += 1
            await db.flush()
    await db.commit()
    return {
        "dry_run": False,
        "profile_key": contract["profile_key"],
        "embedding_model": contract["embedding_model"],
        "embedding_version": contract["embedding_version"],
        "dimensions": dimensions,
        "vector_store": contract["vector_store"],
        "candidate_count": len(chunks),
        "scanned": scanned,
        "embedded": embedded,
        "skipped": skipped,
        "failed_batches": failed_batches,
    }


async def _chunk_embedding_backfill_task_handler(params: dict) -> dict:
    owner_id = int(params.get("owner_id") or params.get("user_id") or 0)
    if owner_id <= 0:
        raise ValueError("owner_id is required for chunk embedding backfill task")
    profile_key = str(
        params.get("embedding_profile") or params.get("profile_key") or DEFAULT_CHUNK_EMBEDDING_PROFILE
    ).strip()
    total_limit = max(1, min(int(params.get("total_limit") or DEFAULT_CHUNK_EMBEDDING_TASK_LIMIT), 2_000_000))
    chunk_limit = max(1, min(int(params.get("chunk_limit") or DEFAULT_CHUNK_EMBEDDING_TASK_CHUNK_LIMIT), 5000))
    batch_size = max(1, min(int(params.get("batch_size") or DEFAULT_CHUNK_EMBEDDING_TASK_BATCH_SIZE), 64))
    priority = int(params.get("priority") or 4)
    task_id = int(params.get("task_id") or 0)
    previous_total = max(0, int(params.get("embedded_total") or 0))

    async with AsyncSessionLocal() as db:
        result = await backfill_chunk_embeddings(
            db,
            owner_id=owner_id,
            profile_key=profile_key,
            dry_run=False,
            limit=chunk_limit,
            batch_size=batch_size,
        )
        counts = await get_chunk_embedding_counts(db, owner_id=owner_id, profile_key=profile_key)
        embedded = int(result.get("embedded") or 0)
        embedded_total = previous_total + embedded
        should_continue = (
            int(counts.get("remaining") or 0) > 0
            and embedded > 0
            and embedded_total < total_limit
        )
        next_task = None
        if should_continue:
            next_task = await enqueue_chunk_embedding_backfill_task(
                db,
                owner_id=owner_id,
                profile_key=profile_key,
                total_limit=total_limit,
                chunk_limit=chunk_limit,
                batch_size=batch_size,
                priority=priority,
                embedded_total=embedded_total,
                exclude_task_id=task_id or None,
            )
        await db.commit()
        return {
            "task_type": CHUNK_EMBEDDING_BACKFILL_TASK_TYPE,
            "owner_id": owner_id,
            "profile_key": profile_key,
            "embedded_total": embedded_total,
            "result": result,
            "counts": counts,
            "continued": bool(next_task and next_task.get("enqueued")),
            "next_task": next_task,
        }


register_task_handler(CHUNK_EMBEDDING_BACKFILL_TASK_TYPE, _chunk_embedding_backfill_task_handler)
