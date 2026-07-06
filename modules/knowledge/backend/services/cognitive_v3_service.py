"""V3 cognitive substrate helpers for knowledge provenance and recall.

This layer is intentionally additive: PostgreSQL remains the source of truth,
existing kb_documents/kb_chunks/kb_raw_data rows are not duplicated, and all
derived indexes can be rebuilt from canonical knowledge artifacts.
"""
from __future__ import annotations

import hashlib
import re
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from app.models.file import File
from sqlalchemy import delete as sa_delete
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import (
    KbArtifactLineage,
    KbCausalCandidate,
    KbContentObject,
    KbDocument,
    KbDocumentProfile,
    KbFactCandidate,
    KbFileKnowledgeLink,
    KbIngestBatch,
    KbPageFusion,
    KbQueryContext,
    KbTerm,
    KbTermEdge,
    KbTermOccurrence,
    KbValidationReport,
)
from .analysis_artifact_service import stable_hash

TERM_SCHEMA_VERSION = "kb_term_graph_v1"

_TOKEN_RE = re.compile(r"[\u4e00-\u9fff]{2,}|[A-Za-z][A-Za-z0-9_+-]{1,}|[A-Z]{1,8}\d{3,}")
_CAUSAL_PATTERNS = (
    re.compile(r"(?:因为|由于|基于)(?P<cause>.{2,80}?)(?:所以|因此|导致|造成|从而|进而)(?P<effect>.{2,100})"),
    re.compile(r"(?P<cause>.{2,80}?)(?:导致|造成|引发|触发|带来|产生|使得)(?P<effect>.{2,100})"),
    re.compile(r"(?:如果|当|一旦)(?P<cause>.{2,80}?)(?:就会|就|会|则|那么)(?P<effect>.{2,100})"),
)


def normalize_term(value: str) -> str:
    """Normalize a term for deterministic local indexing."""
    return re.sub(r"\s+", "", str(value or "").strip().lower())


def extract_terms(text: str, *, limit: int = 80) -> list[str]:
    """Extract lightweight terms without freezing business taxonomies."""
    counts: Counter[str] = Counter()
    for match in _TOKEN_RE.findall(str(text or "")):
        term = match.strip()
        normalized = normalize_term(term)
        if len(normalized) < 2:
            continue
        if normalized in {"这个", "那个", "以及", "或者", "进行", "可以", "需要"}:
            continue
        counts[term] += 1
    return [term for term, _ in counts.most_common(limit)]


def term_hash_parts(term: str) -> dict:
    """Return stable coarse buckets inspired by hash-graph recall, not semantics."""
    normalized = normalize_term(term)
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    language = "mixed"
    if re.fullmatch(r"[\u4e00-\u9fff]+", normalized):
        language = "zh"
    elif re.fullmatch(r"[a-z0-9_+-]+", normalized):
        language = "latin"
    category_seed = f"{language}:{len(normalized)}:{normalized[:1]}:{normalized[-1:]}"
    category_digest = hashlib.sha256(category_seed.encode("utf-8")).hexdigest()
    return {
        "normalized": normalized,
        "language": language,
        "semantic_bucket": int(digest[:4], 16),
        "category_bucket": int(category_digest[:4], 16),
        "exact_hash": digest,
    }


def file_snapshot(file: Any) -> dict:
    name = str(getattr(file, "name", "") or "")
    extension = str(getattr(file, "extension", "") or "").strip(".")
    filename = f"{name}.{extension}" if extension and not name.endswith(f".{extension}") else name
    return {
        "file_id": int(getattr(file, "id", 0) or 0),
        "filename": filename,
        "name": name,
        "extension": extension,
        "folder_id": getattr(file, "folder_id", None),
        "storage_path": getattr(file, "storage_path", None),
        "md5_hash": getattr(file, "md5_hash", None),
        "size": int(getattr(file, "size", 0) or 0),
        "mime_type": str(getattr(file, "mime_type", "") or ""),
    }


def link_payload(link: KbFileKnowledgeLink | None) -> dict | None:
    if link is None:
        return None
    return {
        "link_id": int(link.id),
        "file_id": int(link.file_id),
        "content_object_id": int(link.content_object_id) if link.content_object_id else None,
        "document_id": int(link.document_id) if link.document_id else None,
        "canonical_document_id": int(link.canonical_document_id) if link.canonical_document_id else None,
        "canonical_file_id": int(link.canonical_file_id) if link.canonical_file_id else None,
        "link_role": link.link_role,
        "reuse_reason": link.reuse_reason,
        "md5_hash": link.md5_hash,
        "source_name_snapshot": link.source_name_snapshot,
        "status": link.status,
    }


def _source_hash(kind: str, payload: dict) -> str:
    return stable_hash({"kind": kind, **payload})


async def upsert_content_object(
    db: AsyncSession,
    *,
    owner_id: int,
    file: Any,
    canonical_document: KbDocument | None,
) -> KbContentObject:
    snap = file_snapshot(file)
    md5_hash = snap["md5_hash"]
    sha_key = None if md5_hash else stable_hash({"file_id": snap["file_id"], "storage_path": snap["storage_path"]})
    stmt = select(KbContentObject).where(KbContentObject.owner_id == owner_id)
    if md5_hash:
        stmt = stmt.where(KbContentObject.md5_hash == md5_hash)
    else:
        stmt = stmt.where(KbContentObject.sha256_hash == sha_key)
    content = await db.scalar(stmt.limit(1))
    if content is None:
        content = KbContentObject(owner_id=owner_id, md5_hash=md5_hash, sha256_hash=sha_key)
        db.add(content)
    content.file_size = snap["size"]
    content.mime_type = snap["mime_type"]
    content.extension = snap["extension"]
    if canonical_document is not None:
        content.canonical_document_id = int(canonical_document.id)
        content.canonical_file_id = int(canonical_document.file_id)
    content.status = "active"
    content.diagnostics_json = {
        "schema_version": "kb_content_object_v1",
        "source": "knowledge_v3",
        "has_md5": bool(md5_hash),
    }
    await db.flush()
    return content


async def upsert_file_knowledge_link(
    db: AsyncSession,
    *,
    owner_id: int,
    file: Any,
    document: KbDocument,
    link_role: str,
    reuse_reason: str,
    ingest_batch_id: int | None = None,
) -> KbFileKnowledgeLink:
    content = await upsert_content_object(
        db,
        owner_id=owner_id,
        file=file,
        canonical_document=document,
    )
    snap = file_snapshot(file)
    link = await db.scalar(
        select(KbFileKnowledgeLink).where(
            KbFileKnowledgeLink.owner_id == owner_id,
            KbFileKnowledgeLink.file_id == snap["file_id"],
        ).limit(1)
    )
    if link is None:
        link = KbFileKnowledgeLink(owner_id=owner_id, file_id=snap["file_id"])
        db.add(link)
    link.content_object_id = int(content.id)
    link.document_id = int(document.id)
    link.canonical_document_id = int(document.id)
    link.canonical_file_id = int(document.file_id)
    link.link_role = link_role
    link.reuse_reason = reuse_reason
    link.md5_hash = snap["md5_hash"]
    link.storage_path = snap["storage_path"]
    link.source_name_snapshot = snap["filename"]
    link.source_extension_snapshot = snap["extension"]
    link.source_folder_id = snap["folder_id"]
    link.ingest_batch_id = ingest_batch_id
    link.status = "active"
    link.diagnostics_json = {
        "schema_version": "kb_file_knowledge_link_v1",
        "source": "register_document" if ingest_batch_id is None else "v3_backfill",
    }
    await db.flush()
    return link


async def _canonical_doc_for_file(db: AsyncSession, owner_id: int, file: File) -> KbDocument | None:
    direct = await db.scalar(
        select(KbDocument).where(
            KbDocument.owner_id == owner_id,
            KbDocument.file_id == int(file.id),
            KbDocument.deleted.is_(False),
        ).limit(1)
    )
    if direct is not None:
        return direct
    md5_hash = getattr(file, "md5_hash", None)
    if not md5_hash:
        return None
    return await db.scalar(
        select(KbDocument)
        .join(File, File.id == KbDocument.file_id)
        .where(
            KbDocument.owner_id == owner_id,
            KbDocument.deleted.is_(False),
            File.deleted.is_(False),
            File.md5_hash == md5_hash,
        )
        .order_by(KbDocument.updated_at.desc(), KbDocument.id.desc())
        .limit(1)
    )


async def backfill_cognitive_v3(
    db: AsyncSession,
    *,
    owner_id: int,
    dry_run: bool = True,
    limit: int = 1000,
    source_root: str = "",
    build_terms: bool = True,
) -> dict:
    """Backfill V3 provenance and optional derived indexes from existing rows."""
    limit = max(1, min(int(limit or 1000), 10000))
    files_result = await db.execute(
        select(File)
        .where(File.owner_id == owner_id, File.deleted.is_(False), File.md5_hash.is_not(None))
        .order_by(File.id.asc())
        .limit(limit)
    )
    files = files_result.scalars().all()
    distinct_md5 = {file.md5_hash for file in files if file.md5_hash}
    duplicate_count = sum(max(0, count - 1) for count in Counter(file.md5_hash for file in files if file.md5_hash).values())

    counts = {
        "files_seen": len(files),
        "distinct_md5": len(distinct_md5),
        "canonical_links": 0,
        "duplicate_links": 0,
        "missing_canonical": 0,
        "content_objects": 0,
        "terms": 0,
        "term_occurrences": 0,
        "fact_candidates": 0,
        "causal_candidates": 0,
    }
    if dry_run:
        return {
            "dry_run": True,
            "will_mutate": False,
            "source_root": source_root,
            "duplicate_file_count": duplicate_count,
            **counts,
        }

    batch = KbIngestBatch(
        owner_id=owner_id,
        name="knowledge_v3_backfill",
        source_root=source_root or None,
        source_kind="v3_backfill",
        total_files=len(files),
        distinct_content_count=len(distinct_md5),
        duplicate_file_count=duplicate_count,
        status="running",
        started_at=datetime.now(timezone.utc),
        summary_json={},
    )
    db.add(batch)
    await db.flush()

    touched_docs: set[int] = set()
    for file in files:
        doc = await _canonical_doc_for_file(db, owner_id, file)
        if doc is None:
            counts["missing_canonical"] += 1
            continue
        role = "canonical" if int(doc.file_id) == int(file.id) else "duplicate"
        reason = "canonical_source" if role == "canonical" else "md5_duplicate"
        await upsert_file_knowledge_link(
            db,
            owner_id=owner_id,
            file=file,
            document=doc,
            link_role=role,
            reuse_reason=reason,
            ingest_batch_id=int(batch.id),
        )
        touched_docs.add(int(doc.id))
        if role == "canonical":
            counts["canonical_links"] += 1
        else:
            counts["duplicate_links"] += 1

    counts["content_objects"] = int(await db.scalar(
        select(func.count(KbContentObject.id)).where(KbContentObject.owner_id == owner_id)
    ) or 0)
    if build_terms:
        for document_id in sorted(touched_docs):
            derived = await derive_document_cognitive_index(db, owner_id=owner_id, document_id=document_id, limit=120)
            for key in ("terms", "term_occurrences", "fact_candidates", "causal_candidates"):
                counts[key] += int(derived.get(key, 0))

    batch.status = "done"
    batch.canonical_document_count = counts["canonical_links"]
    batch.failed_count = counts["missing_canonical"]
    batch.completed_at = datetime.now(timezone.utc)
    batch.summary_json = counts
    report = KbValidationReport(
        owner_id=owner_id,
        batch_id=int(batch.id),
        scope="knowledge_v3_backfill",
        report_type="batch_validation",
        status="done" if counts["missing_canonical"] == 0 else "degraded",
        metrics_json=counts,
        findings_json=[
            {"level": "info", "message": "canonical and duplicate file links are explicit"},
            {"level": "warn", "message": "some files had no canonical document"} if counts["missing_canonical"] else {"level": "info", "message": "all files mapped"},
        ],
        recommendations_json=[
            "Review duplicate links before large imports",
            "Use rerun planner for degraded canonical documents",
        ],
        generated_at=datetime.now(timezone.utc),
    )
    db.add(report)
    await db.commit()
    return {
        "dry_run": False,
        "will_mutate": True,
        "batch_id": int(batch.id),
        "validation_report_status": report.status,
        "source_root": source_root,
        "duplicate_file_count": duplicate_count,
        **counts,
    }


async def upsert_term(
    db: AsyncSession,
    *,
    owner_id: int,
    term: str,
    term_type: str = "term",
    source: str = "derived",
    confidence: float = 0.6,
) -> KbTerm:
    parts = term_hash_parts(term)
    existing = await db.scalar(
        select(KbTerm).where(
            KbTerm.owner_id == owner_id,
            KbTerm.normalized == parts["normalized"],
            KbTerm.term_type == term_type,
        ).limit(1)
    )
    item = existing or KbTerm(owner_id=owner_id, term=term, normalized=parts["normalized"], term_type=term_type)
    if existing is None:
        db.add(item)
    item.term = term
    item.language = parts["language"]
    item.semantic_bucket = parts["semantic_bucket"]
    item.category_bucket = parts["category_bucket"]
    item.exact_hash = parts["exact_hash"]
    item.source = source
    item.status = "active"
    item.confidence = confidence
    await db.flush()
    return item


async def derive_document_cognitive_index(
    db: AsyncSession,
    *,
    owner_id: int,
    document_id: int,
    limit: int = 200,
) -> dict:
    """Build lightweight V3 term/fact/causal candidates from existing artifacts."""
    doc = await db.scalar(
        select(KbDocument).where(
            KbDocument.id == document_id,
            KbDocument.owner_id == owner_id,
            KbDocument.deleted.is_(False),
        ).limit(1)
    )
    if doc is None:
        return {"terms": 0, "term_occurrences": 0, "fact_candidates": 0, "causal_candidates": 0}

    for model in (KbTermOccurrence, KbFactCandidate, KbCausalCandidate):
        await db.execute(
            sa_delete(model).where(
                model.owner_id == owner_id,
                model.document_id == document_id,
            )
        )

    profile = await db.scalar(
        select(KbDocumentProfile).where(
            KbDocumentProfile.document_id == document_id,
            KbDocumentProfile.owner_id == owner_id,
        ).order_by(KbDocumentProfile.id.desc()).limit(1)
    )
    fusions = (await db.execute(
        select(KbPageFusion).where(
            KbPageFusion.document_id == document_id,
            KbPageFusion.owner_id == owner_id,
        ).order_by(KbPageFusion.page.asc()).limit(500)
    )).scalars().all()

    source_texts: list[tuple[str, int | None, int | None, str]] = []
    for fusion in fusions:
        text = "\n".join([
            fusion.page_title or "",
            fusion.page_summary or "",
            fusion.fused_text or "",
            " ".join(str(tag) for tag in (fusion.tags_json or []) if tag),
        ]).strip()
        if text:
            source_texts.append((text, int(fusion.page), int(fusion.id), "page_fusion"))
    if profile is not None:
        profile_text = "\n".join([
            profile.subject or "",
            profile.doc_type or "",
            profile.core_conclusions or "",
            profile.doc_summary or "",
            " ".join(str(item) for item in (profile.searchable_phrases or []) if item),
            " ".join(str(item.get("name", "")) for item in (profile.key_entities or []) if isinstance(item, dict)),
        ])
        source_texts.append((profile_text, None, None, "document_profile"))

    term_seen: dict[str, KbTerm] = {}
    occurrence_count = 0
    for text_value, page, fusion_id, source_type in source_texts:
        for position, term in enumerate(extract_terms(text_value, limit=limit)):
            normalized = normalize_term(term)
            if normalized not in term_seen:
                term_seen[normalized] = await upsert_term(
                    db,
                    owner_id=owner_id,
                    term=term,
                    source=source_type,
                    confidence=0.65,
                )
            occurrence = KbTermOccurrence(
                owner_id=owner_id,
                term_id=int(term_seen[normalized].id),
                document_id=document_id,
                page_fusion_id=fusion_id,
                page=page,
                source_type=source_type,
                position=position,
                weight=1.0,
                context=text_value[:500],
                source_hash=_source_hash(
                    "term_occurrence",
                    {
                        "term": normalized,
                        "document_id": document_id,
                        "page": page,
                        "fusion_id": fusion_id,
                        "source": source_type,
                        "position": position,
                    },
                ),
            )
            db.add(occurrence)
            occurrence_count += 1

    terms = list(term_seen.values())
    edge_count = 0
    for left, right in zip(terms, terms[1:]):
        if int(left.id) == int(right.id):
            continue
        source_id, target_id = sorted((int(left.id), int(right.id)))
        edge = await db.scalar(
            select(KbTermEdge).where(
                KbTermEdge.owner_id == owner_id,
                KbTermEdge.source_term_id == source_id,
                KbTermEdge.target_term_id == target_id,
                KbTermEdge.edge_type == "co_occurs",
            ).limit(1)
        )
        if edge is None:
            db.add(KbTermEdge(
                owner_id=owner_id,
                source_term_id=source_id,
                target_term_id=target_id,
                edge_type="co_occurs",
                weight=0.5,
                decision_json={"schema_version": TERM_SCHEMA_VERSION, "source": "document_order"},
            ))
            edge_count += 1

    fact_count = 0
    if profile is not None:
        for label, claim in (
            ("subject", profile.subject),
            ("doc_type", profile.doc_type),
            ("core_conclusions", profile.core_conclusions),
            ("doc_summary", profile.doc_summary),
        ):
            if claim:
                source_hash = _source_hash(
                    "fact_candidate",
                    {
                        "document_id": document_id,
                        "predicate": label,
                        "claim": str(claim),
                        "source": "document_profile",
                    },
                )
                db.add(KbFactCandidate(
                    owner_id=owner_id,
                    document_id=document_id,
                    subject=doc.filename,
                    predicate=label,
                    object_value=str(claim)[:2000],
                    claim_text=str(claim)[:4000],
                    source_type="document_profile",
                    source_hash=source_hash,
                    confidence=profile.confidence or 0.65,
                    diagnostics_json={"schema_version": "kb_fact_candidate_v1", "source_hash": source_hash},
                ))
                fact_count += 1

    causal_count = 0
    for text_value, page, fusion_id, source_type in source_texts:
        for sentence in re.split(r"(?<=[。！？!?；;])|\n+", text_value):
            for pattern in _CAUSAL_PATTERNS:
                match = pattern.search(sentence.strip())
                if not match:
                    continue
                cause = re.sub(r"\s+", " ", match.group("cause")).strip(" ，,。；;：:")
                effect = re.sub(r"\s+", " ", match.group("effect")).strip(" ，,。；;：:")
                if len(cause) < 2 or len(effect) < 2 or cause == effect:
                    continue
                source_hash = _source_hash(
                    "causal_candidate",
                    {
                        "document_id": document_id,
                        "page": page,
                        "cause": cause,
                        "effect": effect,
                        "context": sentence,
                    },
                )
                db.add(KbCausalCandidate(
                    owner_id=owner_id,
                    document_id=document_id,
                    page=page,
                    cause=cause[:500],
                    effect=effect[:500],
                    relation="causal_candidate",
                    context=sentence[:1000],
                    source_hash=source_hash,
                    confidence=0.55,
                    diagnostics_json={
                        "schema_version": "kb_causal_candidate_v1",
                        "source_type": source_type,
                        "page_fusion_id": fusion_id,
                        "source_hash": source_hash,
                    },
                ))
                causal_count += 1
                break

    await db.flush()
    return {
        "terms": len(term_seen),
        "term_occurrences": occurrence_count,
        "term_edges": edge_count,
        "fact_candidates": fact_count,
        "causal_candidates": causal_count,
    }


async def record_artifact_lineage(
    db: AsyncSession,
    *,
    artifact: Any,
    reuse_type: str = "new",
    reused_from_artifact_id: int | None = None,
) -> KbArtifactLineage | None:
    artifact_id = int(getattr(artifact, "id", 0) or 0)
    if artifact_id <= 0:
        return None
    lineage = await db.scalar(
        select(KbArtifactLineage).where(KbArtifactLineage.artifact_id == artifact_id).limit(1)
    )
    if lineage is None:
        lineage = KbArtifactLineage(
            owner_id=int(getattr(artifact, "owner_id", 0) or 0),
            artifact_id=artifact_id,
            document_id=int(getattr(artifact, "document_id", 0) or 0),
            stage=str(getattr(artifact, "stage", "") or ""),
        )
        db.add(lineage)
    lineage.unit_type = str(getattr(artifact, "unit_type", "document") or "document")
    lineage.unit_key = str(getattr(artifact, "unit_key", "document") or "document")
    lineage.source_artifact_ids = getattr(artifact, "source_artifact_ids", None) or []
    lineage.reused_from_artifact_id = reused_from_artifact_id
    lineage.reuse_type = reuse_type
    lineage.input_hash = str(getattr(artifact, "input_hash", "") or "")
    lineage.output_hash = str(getattr(artifact, "output_hash", "") or "")
    lineage.schema_version = str(getattr(artifact, "schema_version", "") or "")
    lineage.diagnostics_json = {"schema_version": "kb_artifact_lineage_v1"}
    await db.flush()
    return lineage


def build_query_context_payload(query: str, results: list[dict]) -> dict:
    expanded_terms = extract_terms(query, limit=24)
    document_ids = sorted({
        int(item.get("document_id"))
        for item in results
        if item.get("document_id") is not None
    })
    evidence_refs = [
        {
            "document_id": item.get("document_id"),
            "chunk_id": item.get("chunk_id"),
            "page": item.get("page"),
            "source": item.get("source") or item.get("retrieval_source") or "hybrid",
            "score": item.get("score"),
        }
        for item in results[:10]
    ]
    facts = [
        {
            "text": str(item.get("text") or "")[:240],
            "document_id": item.get("document_id"),
            "page": item.get("page"),
        }
        for item in results[:5]
        if item.get("text")
    ]
    return {
        "expanded_terms": expanded_terms,
        "related_terms": [],
        "causal_links": [],
        "facts": facts,
        "evidence_refs": evidence_refs,
        "result_document_ids": document_ids,
        "diagnostics": {
            "schema_version": "kb_query_context_v1",
            "strategy": "keyword_vector_term_context",
            "result_count": len(results),
        },
    }


async def _enrich_query_context(
    db: AsyncSession,
    *,
    owner_id: int,
    payload: dict,
) -> None:
    normalized_terms = [normalize_term(term) for term in payload.get("expanded_terms", []) if normalize_term(term)]
    if not normalized_terms:
        return

    terms = (await db.execute(
        select(KbTerm).where(
            KbTerm.owner_id == owner_id,
            KbTerm.normalized.in_(normalized_terms),
            KbTerm.status == "active",
        ).limit(50)
    )).scalars().all()
    term_ids = [int(term.id) for term in terms]
    payload["expanded_terms"] = [
        {
            "term_id": int(term.id),
            "term": term.term,
            "normalized": term.normalized,
            "term_type": term.term_type,
            "semantic_bucket": term.semantic_bucket,
        }
        for term in terms
    ] or payload.get("expanded_terms", [])
    if not term_ids:
        return

    edges = (await db.execute(
        select(KbTermEdge).where(
            KbTermEdge.owner_id == owner_id,
            KbTermEdge.status == "active",
            (KbTermEdge.source_term_id.in_(term_ids) | KbTermEdge.target_term_id.in_(term_ids)),
        ).order_by(KbTermEdge.weight.desc()).limit(30)
    )).scalars().all()
    related_ids = sorted({
        int(edge.source_term_id) if int(edge.source_term_id) not in term_ids else int(edge.target_term_id)
        for edge in edges
    })
    related_terms = []
    if related_ids:
        related_rows = (await db.execute(
            select(KbTerm).where(
                KbTerm.owner_id == owner_id,
                KbTerm.id.in_(related_ids),
            ).limit(30)
        )).scalars().all()
        related_by_id = {int(term.id): term for term in related_rows}
        for edge in edges:
            other_id = int(edge.source_term_id) if int(edge.source_term_id) not in term_ids else int(edge.target_term_id)
            other = related_by_id.get(other_id)
            if other is None:
                continue
            related_terms.append({
                "term_id": other_id,
                "term": other.term,
                "edge_type": edge.edge_type,
                "weight": edge.weight,
            })
    payload["related_terms"] = related_terms[:20]

    document_ids = [int(value) for value in payload.get("result_document_ids", []) if value]
    if not document_ids:
        return
    facts = (await db.execute(
        select(KbFactCandidate).where(
            KbFactCandidate.owner_id == owner_id,
            KbFactCandidate.document_id.in_(document_ids),
            KbFactCandidate.status == "candidate",
        ).order_by(KbFactCandidate.id.desc()).limit(20)
    )).scalars().all()
    causal = (await db.execute(
        select(KbCausalCandidate).where(
            KbCausalCandidate.owner_id == owner_id,
            KbCausalCandidate.document_id.in_(document_ids),
            KbCausalCandidate.status == "candidate",
        ).order_by(KbCausalCandidate.id.desc()).limit(20)
    )).scalars().all()
    if facts:
        payload["facts"] = [
            {
                "fact_id": int(item.id),
                "document_id": int(item.document_id),
                "page": item.page,
                "subject": item.subject,
                "predicate": item.predicate,
                "claim_text": item.claim_text[:500],
                "confidence": item.confidence,
            }
            for item in facts
        ]
    payload["causal_links"] = [
        {
            "causal_id": int(item.id),
            "document_id": int(item.document_id),
            "page": item.page,
            "cause": item.cause,
            "effect": item.effect,
            "confidence": item.confidence,
        }
        for item in causal
    ]


async def persist_query_context(
    db: AsyncSession,
    *,
    owner_id: int,
    query: str,
    results: list[dict],
) -> dict:
    payload = build_query_context_payload(query, results)
    await _enrich_query_context(db, owner_id=owner_id, payload=payload)
    normalized = normalize_term(query)
    row = KbQueryContext(
        owner_id=owner_id,
        query=query,
        normalized_query=normalized,
        query_hash=hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
        expanded_terms=payload["expanded_terms"],
        related_terms=payload["related_terms"],
        causal_links=payload["causal_links"],
        facts=payload["facts"],
        evidence_refs=payload["evidence_refs"],
        result_document_ids=payload["result_document_ids"],
        diagnostics_json=payload["diagnostics"],
    )
    db.add(row)
    await db.flush()
    payload["query_context_id"] = int(row.id)
    return payload
