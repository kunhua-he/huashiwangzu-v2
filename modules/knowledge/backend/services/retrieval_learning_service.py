"""Implicit retrieval feedback and ranking priors.

This is the knowledge-side half of a Hermes-like memory loop: query traces are
already persisted in ``kb_query_contexts``; background Agent/cron code can pass
later conversation excerpts here, and this service turns them into durable
retrieval learning events.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re

from sqlalchemy import and_, bindparam, select
from sqlalchemy import text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import KbChunk, KbDocument, KbDocumentProfile, KbQueryContext, KbRetrievalLearningEvent
from .cognitive_index_service import normalize_term

logger = logging.getLogger("v2.knowledge").getChild("retrieval_learning")

RETRIEVAL_LEARNING_VERSION = "kb_retrieval_learning_v1"
RETRIEVAL_REFLECTION_TIMEOUT_SECONDS = 45.0
RETRIEVAL_REFLECTION_MAX_EVENTS = 20


def _clamp(value: object, low: float, high: float, default: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return max(low, min(high, number))


def _json_dumps(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _stable_event_hash(payload: dict) -> str:
    return hashlib.sha256(_json_dumps(payload).encode("utf-8")).hexdigest()


def _query_hash(normalized_query: str) -> str:
    return hashlib.sha256(normalized_query.encode("utf-8")).hexdigest()


def _extract_json_object(text: str) -> dict | None:
    raw = str(text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?", "", raw, flags=re.I).strip()
        raw = re.sub(r"```$", "", raw).strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, flags=re.S)
        if not match:
            return None
        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return parsed if isinstance(parsed, dict) else None


def _query_terms_from_plan(query_plan: dict | None) -> list[str]:
    terms: list[str] = []
    if not isinstance(query_plan, dict):
        return terms
    for key in ("terms", "entities", "document_types", "constraints"):
        values = query_plan.get(key)
        if not isinstance(values, list):
            continue
        for value in values:
            normalized = normalize_term(str(value or ""))
            if normalized and normalized not in terms:
                terms.append(normalized)
    return terms[:24]


async def _build_candidate_digest(
    db: AsyncSession,
    *,
    owner_id: int,
    context: KbQueryContext,
    diagnostics: dict,
) -> list[dict]:
    """Build a readable, bounded candidate summary for reflection."""
    score_breakdowns = diagnostics.get("score_breakdowns") if isinstance(diagnostics, dict) else []
    snapshots = diagnostics.get("candidate_snapshots") if isinstance(diagnostics, dict) else []
    by_key: dict[tuple[int | None, int | None], dict] = {}
    ordered: list[dict] = []

    for item in (score_breakdowns or [])[:10]:
        if not isinstance(item, dict):
            continue
        candidate = {
            "document_id": item.get("document_id"),
            "chunk_id": item.get("chunk_id"),
            "rank": item.get("final_rank"),
            "retrieval_score": item.get("retrieval_score"),
            "source": item.get("retrieval_source"),
        }
        key = (candidate["document_id"], candidate["chunk_id"])
        by_key[key] = candidate
        ordered.append(candidate)

    if not ordered:
        for rank, document_id in enumerate((context.result_document_ids or [])[:10], start=1):
            candidate = {
                "document_id": document_id,
                "chunk_id": None,
                "rank": rank,
                "retrieval_score": None,
                "source": "query_context",
            }
            by_key[(document_id, None)] = candidate
            ordered.append(candidate)

    for item in (snapshots or [])[:20]:
        if not isinstance(item, dict):
            continue
        key = (item.get("document_id"), item.get("chunk_id"))
        candidate = by_key.get(key)
        if candidate is None and item.get("document_id") is not None:
            candidate = by_key.get((item.get("document_id"), None))
        if candidate is None:
            continue
        candidate.update({
            "filename": item.get("filename"),
            "extension": item.get("extension"),
            "page": item.get("page"),
            "text": str(item.get("text") or "")[:700],
            "block_type": item.get("block_type"),
        })

    document_ids = sorted({
        int(item["document_id"])
        for item in ordered
        if item.get("document_id") is not None and str(item.get("document_id")).isdigit()
    })
    chunk_ids = sorted({
        int(item["chunk_id"])
        for item in ordered
        if item.get("chunk_id") is not None and str(item.get("chunk_id")).isdigit()
    })

    docs: dict[int, dict] = {}
    if document_ids:
        rows = (await db.execute(
            select(
                KbDocument.id,
                KbDocument.filename,
                KbDocument.extension,
                KbDocument.summary,
                KbDocument.total_pages,
                KbDocumentProfile.subject,
                KbDocumentProfile.doc_type,
                KbDocumentProfile.doc_summary,
                KbDocumentProfile.core_conclusions,
            )
            .outerjoin(
                KbDocumentProfile,
                and_(
                    KbDocumentProfile.document_id == KbDocument.id,
                    KbDocumentProfile.owner_id == KbDocument.owner_id,
                ),
            )
            .where(
                KbDocument.owner_id == owner_id,
                KbDocument.id.in_(document_ids),
                KbDocument.deleted.is_(False),
            )
        )).mappings().all()
        docs = {int(row["id"]): dict(row) for row in rows}

    chunks: dict[int, dict] = {}
    if chunk_ids:
        rows = (await db.execute(
            select(KbChunk.id, KbChunk.page, KbChunk.block_type, KbChunk.text)
            .where(
                KbChunk.owner_id == owner_id,
                KbChunk.id.in_(chunk_ids),
            )
        )).mappings().all()
        chunks = {int(row["id"]): dict(row) for row in rows}

    for item in ordered:
        document_id = item.get("document_id")
        doc = docs.get(int(document_id)) if document_id is not None and str(document_id).isdigit() else None
        if doc:
            if not item.get("filename"):
                item["filename"] = doc.get("filename")
            if not item.get("extension"):
                item["extension"] = doc.get("extension")
            item["subject"] = doc.get("subject")
            item["doc_type"] = doc.get("doc_type")
            item["doc_summary"] = str(doc.get("doc_summary") or doc.get("summary") or "")[:700]
            item["core_conclusions"] = str(doc.get("core_conclusions") or "")[:700]
            item["total_pages"] = doc.get("total_pages")
        chunk_id = item.get("chunk_id")
        chunk = chunks.get(int(chunk_id)) if chunk_id is not None and str(chunk_id).isdigit() else None
        if chunk:
            if item.get("page") is None:
                item["page"] = chunk.get("page")
            if not item.get("block_type"):
                item["block_type"] = chunk.get("block_type")
            if not item.get("text"):
                item["text"] = str(chunk.get("text") or "")[:700]
    return ordered


def _coerce_event(raw: dict, *, allowed_document_ids: set[int]) -> dict | None:
    document_id_raw = raw.get("document_id")
    try:
        document_id = int(document_id_raw) if document_id_raw is not None else None
    except (TypeError, ValueError):
        document_id = None
    if document_id is not None and allowed_document_ids and document_id not in allowed_document_ids:
        return None

    chunk_id = None
    if raw.get("chunk_id") is not None:
        try:
            chunk_id = int(raw.get("chunk_id"))
        except (TypeError, ValueError):
            chunk_id = None

    signal_type = str(raw.get("signal_type") or "implicit_feedback").strip()[:64]
    signal_score = _clamp(raw.get("signal_score"), -1.0, 1.0, 0.0)
    confidence = _clamp(raw.get("confidence"), 0.0, 1.0, 0.5)
    reason = str(raw.get("reason") or "").strip()[:2000]
    evidence = raw.get("evidence")
    if not isinstance(evidence, dict):
        evidence = {"raw": str(evidence or "")[:1000]} if evidence else {}
    return {
        "document_id": document_id,
        "chunk_id": chunk_id,
        "signal_type": signal_type or "implicit_feedback",
        "signal_score": signal_score,
        "confidence": confidence,
        "reason": reason,
        "evidence": evidence,
    }


async def record_retrieval_learning_events(
    db: AsyncSession,
    *,
    owner_id: int,
    events: list[dict],
    query_context_id: int | None = None,
    query: str = "",
    query_plan: dict | None = None,
    source: str = "llm_reflection",
    model_used: str | None = None,
) -> dict:
    """Persist implicit retrieval feedback events idempotently."""
    context: KbQueryContext | None = None
    if query_context_id:
        context = await db.scalar(
            select(KbQueryContext).where(
                KbQueryContext.id == int(query_context_id),
                KbQueryContext.owner_id == owner_id,
            ).limit(1)
        )
    normalized_query = normalize_term(query or (context.query if context else ""))
    query_hash = (
        str(context.query_hash or "")
        if context is not None and context.query_hash
        else _query_hash(normalized_query)
    )
    allowed_document_ids = {
        int(value)
        for value in (context.result_document_ids or [])
        if isinstance(value, int | str) and str(value).isdigit()
    } if context is not None else set()

    inserted = 0
    updated = 0
    skipped = 0
    persisted: list[dict] = []
    for raw in events[:RETRIEVAL_REFLECTION_MAX_EVENTS]:
        if not isinstance(raw, dict):
            skipped += 1
            continue
        event = _coerce_event(raw, allowed_document_ids=allowed_document_ids)
        if event is None:
            skipped += 1
            continue
        source_hash = _stable_event_hash({
            "version": RETRIEVAL_LEARNING_VERSION,
            "owner_id": owner_id,
            "query_context_id": query_context_id,
            "query_hash": query_hash,
            "document_id": event["document_id"],
            "chunk_id": event["chunk_id"],
            "signal_type": event["signal_type"],
            "reason": event["reason"][:300],
            "source": source,
        })
        existing = await db.scalar(
            select(KbRetrievalLearningEvent).where(
                KbRetrievalLearningEvent.owner_id == owner_id,
                KbRetrievalLearningEvent.source_hash == source_hash,
            ).limit(1)
        )
        if existing is None:
            existing = KbRetrievalLearningEvent(
                owner_id=owner_id,
                query_context_id=query_context_id,
                query_hash=query_hash,
                normalized_query=normalized_query,
                document_id=event["document_id"],
                chunk_id=event["chunk_id"],
                source_hash=source_hash,
            )
            db.add(existing)
            inserted += 1
        else:
            updated += 1
        existing.signal_type = event["signal_type"]
        existing.signal_score = event["signal_score"]
        existing.confidence = event["confidence"]
        existing.source = source[:64]
        existing.reason = event["reason"]
        existing.evidence_json = {
            "schema_version": RETRIEVAL_LEARNING_VERSION,
            "query_plan": query_plan or (context.diagnostics_json or {}).get("query_plan") if context else query_plan,
            "evidence": event["evidence"],
        }
        existing.model_used = model_used
        existing.status = "active"
        persisted.append({
            "document_id": event["document_id"],
            "chunk_id": event["chunk_id"],
            "signal_type": event["signal_type"],
            "signal_score": event["signal_score"],
            "confidence": event["confidence"],
        })

    await db.flush()
    return {
        "schema_version": RETRIEVAL_LEARNING_VERSION,
        "query_context_id": query_context_id,
        "inserted": inserted,
        "updated": updated,
        "skipped": skipped,
        "events": persisted,
    }


async def reflect_retrieval_feedback(
    db: AsyncSession,
    *,
    owner_id: int,
    query_context_id: int,
    conversation_excerpt: str,
    source: str = "agent_background_reflection",
) -> dict:
    """Ask the model to infer retrieval feedback from later conversation text."""
    context = await db.scalar(
        select(KbQueryContext).where(
            KbQueryContext.id == int(query_context_id),
            KbQueryContext.owner_id == owner_id,
        ).limit(1)
    )
    if context is None:
        return {"error": "query_context_not_found", "query_context_id": query_context_id, "events": []}

    diagnostics = context.diagnostics_json or {}
    candidate_digest = await _build_candidate_digest(
        db,
        owner_id=owner_id,
        context=context,
        diagnostics=diagnostics if isinstance(diagnostics, dict) else {},
    )
    messages = [
        {
            "role": "system",
            "content": (
                "你是企业知识库检索质量复盘器。只返回 JSON，不要解释。"
                "不要依赖用户点击反馈；根据后续对话判断本次检索结果是否帮到了用户。"
                "signal_score 范围 -1 到 1：正数表示该文档/块更应被类似查询召回，负数表示应降权。"
                "只评价候选列表中出现过的 document_id/chunk_id；证据不足则返回空 events。"
            ),
        },
        {
            "role": "user",
            "content": (
                "请分析一次知识库检索后的隐式反馈。\n"
                f"查询: {context.query}\n"
                f"检索计划: {_json_dumps(diagnostics.get('query_plan') if isinstance(diagnostics, dict) else {})}\n"
                f"候选结果: {_json_dumps(candidate_digest)}\n"
                f"证据引用: {_json_dumps((context.evidence_refs or [])[:10])}\n"
                f"后续对话片段:\n{conversation_excerpt[:8000]}\n\n"
                "返回 JSON: {\"events\":[{\"document_id\":1,\"chunk_id\":2,"
                "\"signal_type\":\"helpful|wrong_result|missing_expected|followup_used|reformulated\","
                "\"signal_score\":0.7,\"confidence\":0.8,\"reason\":\"依据\","
                "\"evidence\":{\"excerpt\":\"短证据\"}}]}"
            ),
        },
    ]
    try:
        from app.gateway.router import gateway_router

        result = await asyncio.wait_for(
            gateway_router.chat(messages=messages),
            timeout=RETRIEVAL_REFLECTION_TIMEOUT_SECONDS,
        )
        content = str(result.get("content") or "")
        if result.get("error") or not content:
            raise RuntimeError(str(result.get("error") or "empty reflection"))
        parsed = _extract_json_object(content) or {}
        raw_events = parsed.get("events") if isinstance(parsed.get("events"), list) else []
        write_result = await record_retrieval_learning_events(
            db,
            owner_id=owner_id,
            query_context_id=int(context.id),
            query=context.query,
            query_plan=diagnostics.get("query_plan") if isinstance(diagnostics, dict) else None,
            events=raw_events,
            source=source,
            model_used=str(result.get("model") or result.get("model_used") or ""),
        )
        return {
            "query_context_id": int(context.id),
            "query": context.query,
            "llm_source": "gateway",
            **write_result,
        }
    except Exception as exc:
        logger.warning("retrieval feedback reflection failed: %s", exc)
        return {
            "query_context_id": int(context.id),
            "query": context.query,
            "error": str(exc),
            "events": [],
            "inserted": 0,
            "updated": 0,
            "skipped": 0,
        }


async def get_learning_priors_for_documents(
    db: AsyncSession,
    *,
    owner_id: int,
    query_plan: dict | None,
    document_ids: list[int],
) -> dict[int, dict]:
    """Return signed retrieval priors for candidate documents."""
    if not document_ids:
        return {}
    query_text = ""
    if isinstance(query_plan, dict):
        query_text = str(query_plan.get("query") or query_plan.get("original_query") or "")
    normalized_query = normalize_term(query_text)
    exact_hash = _query_hash(normalized_query) if normalized_query else ""
    terms = _query_terms_from_plan(query_plan)

    stmt = sa_text(
        """
        WITH doc_ids AS (
            SELECT CAST(value AS bigint) AS document_id
            FROM unnest(CAST(:document_ids AS bigint[])) AS value
        ),
        events AS (
            SELECT
                e.document_id,
                e.signal_score,
                e.confidence,
                CASE
                    WHEN :query_hash != '' AND e.query_hash = :query_hash THEN 1.0
                    WHEN e.normalized_query = ANY(CAST(:terms AS text[])) THEN 0.55
                    ELSE 0.25
                END AS query_weight
            FROM kb_retrieval_learning_events e
            JOIN doc_ids ids ON ids.document_id = e.document_id
            WHERE e.owner_id = :owner_id
              AND e.status = 'active'
              AND e.document_id IS NOT NULL
        )
        SELECT
            document_id,
            count(*) AS event_count,
            sum(signal_score * confidence * query_weight) AS weighted_sum,
            sum(confidence * query_weight) AS weight_sum
        FROM events
        GROUP BY document_id
        """
    ).bindparams(bindparam("document_ids", expanding=False), bindparam("terms", expanding=False))
    rows = (await db.execute(
        stmt,
        {
            "owner_id": owner_id,
            "document_ids": sorted({int(value) for value in document_ids}),
            "query_hash": exact_hash,
            "terms": terms or [normalized_query or "__none__"],
        },
    )).mappings().all()
    priors: dict[int, dict] = {}
    for row in rows:
        weight_sum = float(row["weight_sum"] or 0.0)
        weighted_sum = float(row["weighted_sum"] or 0.0)
        prior = 0.0 if weight_sum <= 0 else max(-1.0, min(1.0, weighted_sum / weight_sum))
        priors[int(row["document_id"])] = {
            "prior": round(prior, 4),
            "event_count": int(row["event_count"] or 0),
        }
    return priors
