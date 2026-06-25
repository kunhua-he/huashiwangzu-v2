"""知识库混合检索服务：向量检索 + 关键词检索 + RRF 融合排序 + Evidence planner。"""
import logging
import math
import time
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select, or_, and_, func, text, Float, cast
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.services.model_services import get_embedding, rerank
from app.gateway.router import gateway_router

logger = logging.getLogger("v2.knowledge").getChild("search")

# RRF 常数
RRF_K = 60

# ── Evidence-oriented query surface ──────────────────────────────────

EVIDENCE_SYSTEM_PROMPT = """你是一个知识库检索规划专家。你的工作是：
1. 判断用户的查询是否可回答（基于当前检索结果）
2. 如果检索结果不足，输出 query rewrite 建议
3. 对可回答的查询，给出 answerability 等级和证据摘要

输出严格 JSON（不要 markdown 代码块标记）：
{
  "answerable": "yes|weak|no",
  "answerability_reason": "简短原因",
  "rewritten_query": "重写后的查询文本（如果原查询不够好）或原样返回",
  "multi_hop": false,
  "confidence": 0.85
}

answerable:
  - "yes": 检索结果充分，可直接回答
  - "weak": 检索结果部分相关，需要更多上下文才能确定
  - "no": 检索结果不相关或为空，应告知用户无法回答
"""


@dataclass
class QueryRewriteResult:
    """Result of query rewrite analysis."""
    original: str
    rewritten: str
    multi_hop: bool
    confidence: float
    reason: str


@dataclass
class AnswerabilityJudgment:
    """Judgment on whether a query can be answered from retrieved evidence."""
    answerable: str  # "yes" | "weak" | "no"
    reason: str
    confidence: float


@dataclass
class EvidenceCitation:
    """A single citation within an evidence packet."""
    chunk_id: int
    document_id: int
    page: int | None
    text: str
    score: float
    source: str  # "keyword" | "vector" | "fusion" | "graph"
    provenance: str  # document name or page summary


@dataclass
class EvidencePacket:
    """Unified evidence packet combining search results, fusion, and graph context.

    This is the primary output of the evidence-oriented knowledge surface.
    Agent consumers inspect ``answerable`` and ``citations`` instead of
    raw text chunks.
    """
    query: str
    answerable: str  # "yes" | "weak" | "no"
    answerability_reason: str
    citations: list[EvidenceCitation]
    citation_count: int
    fusion_context: list[dict] = field(default_factory=list)
    graph_context: list[dict] = field(default_factory=list)
    rewritten_query: str | None = None
    confidence: float = 0.0
    timing_ms: float = 0.0


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """计算两个向量的余弦相似度。"""
    if not vec_a or not vec_b:
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


async def keyword_search(db: AsyncSession, query: str, owner_id: int, top_k: int = 20) -> list[dict]:
    """关键词全文检索（ILIKE on text + keywords）。"""
    from ..models import KbChunk

    if not query.strip():
        return []

    terms = [t.strip() for t in query.split() if len(t.strip()) >= 1]
    if not terms:
        return []

    # 构建 ILIKE 条件
    conditions = []
    for term in terms:
        pattern = f"%{term}%"
        conditions.append(
            or_(
                KbChunk.text.ilike(pattern),
                KbChunk.keywords.ilike(pattern),
            )
        )

    clause = and_(*conditions) if len(conditions) > 1 else conditions[0]
    stmt = (
        select(KbChunk)
        .where(clause, KbChunk.owner_id == owner_id)
        .order_by(KbChunk.id.desc())
        .limit(top_k * 2)
    )
    r = await db.execute(stmt)
    chunks = r.scalars().all()

    results = []
    for i, ch in enumerate(chunks):
        # 计算关键词得分：匹配词越多得分越高
        score = 0.0
        matched_terms = 0
        for term in terms:
            if term.lower() in (ch.text or "").lower():
                score += 1.0
                matched_terms += 1
            elif ch.keywords and term.lower() in ch.keywords.lower():
                score += 0.5
                matched_terms += 0.5

        # tf 近似：词频越高分越高（限制在文本中）
        text_lower = (ch.text or "").lower()
        for term in terms:
            tf = text_lower.count(term.lower())
            if tf > 0:
                score += math.log(1 + tf) * 0.3

        results.append({
            "chunk_id": ch.id,
            "document_id": ch.document_id,
            "page": ch.page,
            "block_type": ch.block_type,
            "text": ch.text[:500],
            "keywords": ch.keywords,
            "score": round(score, 4),
            "rank": i + 1,
            "source": "keyword",
        })

    # 按得分排序取 top_k
    results.sort(key=lambda x: -x["score"])
    return results[:top_k]


async def vector_search(db: AsyncSession, query: str, owner_id: int, top_k: int = 20) -> list[dict]:
    """向量检索：用 query embedding 与已存储 chunk embedding 计算余弦相似度。"""
    from ..models import KbChunk

    # 获取 query 向量
    try:
        query_emb = await get_embedding(query)
    except Exception as e:
        logger.warning("get_embedding failed for query '%s': %s", query[:50], e)
        return []

    if not query_emb:
        return []

    # 查询有 embedding 的 chunk（移除硬上限，大文档也能召全）
    stmt = (
        select(KbChunk)
        .where(KbChunk.owner_id == owner_id, KbChunk.embedding.isnot(None))
    )
    r = await db.execute(stmt)
    chunks = r.scalars().all()

    scored = []
    for ch in chunks:
        if not ch.embedding:
            continue
        sim = cosine_similarity(query_emb, ch.embedding)
        if sim > 0.0:
            scored.append({
                "chunk_id": ch.id,
                "document_id": ch.document_id,
                "page": ch.page,
                "block_type": ch.block_type,
                "text": ch.text[:500],
                "keywords": ch.keywords,
                "score": round(sim, 4),
                "rank": 0,
                "source": "vector",
            })

    scored.sort(key=lambda x: -x["score"])
    for i, item in enumerate(scored):
        item["rank"] = i + 1

    return scored[:top_k]


def rrf_fusion(keyword_results: list[dict], vector_results: list[dict], top_k: int = 10) -> list[dict]:
    """RRF 融合排序：合并关键词和向量检索结果。"""
    # 用 chunk_id 去重
    seen: set[int] = set()
    fused: list[dict] = []

    for item in keyword_results + vector_results:
        cid = item["chunk_id"]
        if cid in seen:
            continue
        seen.add(cid)

        kw_score = item["score"]
        vec_score = item["score"]

        # 找在另一组中的排名
        kw_rank = None
        vec_rank = None
        for kw in keyword_results:
            if kw["chunk_id"] == cid:
                kw_rank = kw["rank"]
                kw_score = kw["score"]
                break
        for vec in vector_results:
            if vec["chunk_id"] == cid:
                vec_rank = vec["rank"]
                vec_score = vec["score"]
                break

        # RRF 分数
        rrf = 0.0
        if kw_rank:
            rrf += 1.0 / (RRF_K + kw_rank)
        if vec_rank:
            rrf += 1.0 / (RRF_K + vec_rank)

        fused.append({
            **item,
            "rrf_score": round(rrf, 4),
            "kw_score": kw_score,
            "vec_score": vec_score,
            "kw_rank": kw_rank,
            "vec_rank": vec_rank,
        })

    fused.sort(key=lambda x: -x["rrf_score"])
    for i, item in enumerate(fused):
        item["final_rank"] = i + 1

    return fused[:top_k]


async def hybrid_search(
    db: AsyncSession,
    query: str,
    owner_id: int,
    top_k: int = 10,
    use_rerank: bool = False,
) -> list[dict]:
    """混合检索：向量 + 关键词 → RRF 融合 → 可选 rerank。"""
    # 并行关键词和向量检索
    kw_results = await keyword_search(db, query, owner_id, top_k=top_k * 2)
    vec_results = await vector_search(db, query, owner_id, top_k=top_k * 2)

    # RRF 融合
    results = rrf_fusion(kw_results, vec_results, top_k=top_k * 2)

    # 可选 rerank
    if use_rerank and results:
        try:
            docs = [r["text"] for r in results]
            reranked = await rerank(query, docs, top_k=top_k)
            rerank_map = {}
            for i, rr in enumerate(reranked):
                idx = rr.get("index")
                score = rr.get("relevance_score", 0)
                if idx is not None and idx < len(results):
                    rerank_map[idx] = score
            for i, r in enumerate(results):
                if i in rerank_map:
                    r["rerank_score"] = rerank_map[i]
            results.sort(key=lambda x: -(x.get("rerank_score", 0) or 0))
            for i, r in enumerate(results):
                r["final_rank"] = i + 1
        except Exception as e:
            logger.warning("Rerank failed (non-fatal): %s", e)

    return results[:top_k]


# ── Query Rewrite ───────────────────────────────────────────────────────


async def _rewrite_query(query: str, profile_key: str = "deepseek-v4-flash") -> QueryRewriteResult:
    """Use LLM to rewrite the search query for better retrieval."""
    if not query.strip():
        return QueryRewriteResult(query, query, multi_hop=False, confidence=1.0, reason="empty query")

    try:
        messages = [
            {"role": "system", "content": """You are a search query rewriting expert. Given a user query, produce a better search query.

Rules:
1. Expand abbreviations and acronyms
2. Add domain-appropriate synonyms
3. Break compound questions into simpler terms
4. Keep the rewritten query concise (< 200 chars)
5. Return JSON only: {"rewritten": "...", "multi_hop": false, "reason": "..."}"""},
            {"role": "user", "content": f"Query: {query}"},
        ]
        resp = await gateway_router.chat(messages, profile_key=profile_key)
        content = (resp.get("content") or "").strip()
        if content.startswith("```"):
            lines = content.splitlines()
            content = "\n".join(lines[1:-1]) if len(lines) > 2 else content
        import json
        parsed = json.loads(content)
        rewritten = parsed.get("rewritten", query)
        multi_hop = parsed.get("multi_hop", False)
        reason = parsed.get("reason", "rewritten for better recall")
        confidence = 0.8
        return QueryRewriteResult(query, rewritten, multi_hop, confidence, reason)
    except Exception as e:
        logger.warning("query rewrite failed (non-fatal): %s", e)
        return QueryRewriteResult(query, query, multi_hop=False, confidence=0.5, reason=f"rewrite failed: {e}")


# ── Answerability Judgment ───────────────────────────────────────────────


async def _judge_answerability(
    query: str,
    results: list[dict],
    profile_key: str = "deepseek-v4-flash",
) -> AnswerabilityJudgment:
    """Judge whether the query can be answered from retrieved results."""
    if not query.strip() or not results:
        return AnswerabilityJudgment("no", "no relevant results retrieved", 0.0)

    # Quick heuristic: if top result has high similarity, skip LLM call
    top_sim = max((r.get("rrf_score", r.get("similarity", 0)) or 0) for r in results[:3]) if results else 0
    if top_sim > 0.7 and len(results) >= 2:
        return AnswerabilityJudgment("yes", f"high-confidence result (sim={top_sim:.2f})", min(1.0, top_sim))

    if top_sim < 0.2:
        return AnswerabilityJudgment("no", f"low similarity (sim={top_sim:.2f}), cannot answer", top_sim)

    try:
        snippets = "\n\n".join([r.get("text", "")[:300] for r in results[:3]])
        messages = [
            {"role": "system", "content": EVIDENCE_SYSTEM_PROMPT},
            {"role": "user", "content": f"Query: {query}\n\nRetrieved results:\n{snippets}"},
        ]
        resp = await gateway_router.chat(messages, profile_key=profile_key)
        content = (resp.get("content") or "").strip()
        if content.startswith("```"):
            lines = content.splitlines()
            content = "\n".join(lines[1:-1]) if len(lines) > 2 else content
        import json
        parsed = json.loads(content)
        answerable = parsed.get("answerable", "weak")
        reason = parsed.get("answerability_reason", "LLM judgment")
        confidence = parsed.get("confidence", 0.5)
        return AnswerabilityJudgment(answerable, reason, confidence)
    except Exception as e:
        logger.warning("answerability judgment failed (non-fatal): %s", e)
        return AnswerabilityJudgment("weak", f"judgment failed: {e}", 0.3)


# ── Evidence Packet Builder ──────────────────────────────────────────────


def _build_evidence_packet(
    query: str,
    results: list[dict],
    judgment: AnswerabilityJudgment,
    rewrite: QueryRewriteResult | None = None,
    fusion_context: list[dict] | None = None,
    graph_context: list[dict] | None = None,
    start_time: float | None = None,
) -> EvidencePacket:
    """Build a unified evidence packet from search results + optional fusion + graph."""
    citations = []
    for r in results:
        provenance = r.get("document_name", "") or ""
        if not provenance:
            pf = r.get("page_fusion")
            if isinstance(pf, dict):
                provenance = pf.get("page_summary", "") or ""
        citations.append(EvidenceCitation(
            chunk_id=r.get("chunk_id", 0),
            document_id=r.get("document_id", 0),
            page=r.get("page"),
            text=r.get("text", "")[:500],
            score=r.get("rrf_score", r.get("similarity", 0)) or 0,
            source=r.get("source", "keyword"),
            provenance=provenance,
        ))

    timing = (time.time() - start_time) * 1000 if start_time else 0.0

    return EvidencePacket(
        query=query,
        answerable=judgment.answerable,
        answerability_reason=judgment.reason,
        citations=citations,
        citation_count=len(citations),
        fusion_context=fusion_context or [],
        graph_context=graph_context or [],
        rewritten_query=rewrite.rewritten if rewrite else None,
        confidence=judgment.confidence,
        timing_ms=round(timing, 1),
    )


async def evidence_oriented_search(
    db: AsyncSession,
    query: str,
    owner_id: int,
    top_k: int = 10,
    use_rerank: bool = False,
    enable_rewrite: bool = True,
    enable_answerability: bool = True,
    include_fusion: bool = True,
    include_graph: bool = True,
) -> dict:
    """Evidence-oriented search: the primary knowledge surface for agents.

    This wraps ``hybrid_search`` with:
    1. Query rewrite (optional)
    2. Hybrid search (keyword + vector + RRF + optional rerank)
    3. Answerability judgment
    4. Evidence packet assembly (citations + fusion + graph context)

    Returns a dict with ``evidence_packet`` (serialised ``EvidencePacket``)
    and raw metadata.
    """
    _t0 = time.time()

    # 1. Query rewrite
    rewrite = None
    if enable_rewrite:
        rewrite = await _rewrite_query(query)
        search_query = rewrite.rewritten
    else:
        search_query = query

    # 2. Hybrid search
    results = await hybrid_search(db, search_query, owner_id, top_k=top_k + 5, use_rerank=use_rerank)

    # 2b. Enrich results with document names for citation provenance
    if results:
        from ..models import KbDocument
        doc_ids = list(set(r.get("document_id") for r in results if r.get("document_id")))
        if doc_ids:
            doc_stmt = select(KbDocument.id, KbDocument.filename).where(
                KbDocument.id.in_(doc_ids), KbDocument.owner_id == owner_id
            )
            doc_r = await db.execute(doc_stmt)
            doc_map = {row.id: row.filename for row in doc_r.all()}
            for r in results:
                r["document_name"] = doc_map.get(r.get("document_id", 0), "")
        else:
            for r in results:
                r["document_name"] = ""

    # 3. Fusion context (page-level fusion for top results)
    fusion_context = []
    if include_fusion and results:
        from .fusion_service import get_page_fusion_detail as _get_fusion_detail
        seen_fusions: set[tuple[int, int]] = set()
        for r in results[:5]:
            doc_id = r.get("document_id")
            page = r.get("page")
            if doc_id and page and (doc_id, page) not in seen_fusions:
                seen_fusions.add((doc_id, page))
                try:
                    fusion = await _get_fusion_detail(db, doc_id, page)
                    if fusion:
                        fusion_context.append(fusion)
                except Exception as e:
                    logger.debug("fusion fetch skipped for doc=%d page=%d: %s", doc_id, page, e)

    # 4. Graph context (entity relationships for top documents)
    graph_context = []
    if include_graph and results:
        from .entity_service import get_evidence_graph_context as _get_graph_ctx
        seen_doc_ids = list(set(r.get("document_id") for r in results[:5] if r.get("document_id")))
        try:
            graph_context = await _get_graph_ctx(db, owner_id, seen_doc_ids, max_nodes=5)
        except Exception as e:
            logger.debug("graph context skipped: %s", e)

    # 5. Answerability judgment
    judgment = AnswerabilityJudgment("weak", "skipped", 0.5)
    if enable_answerability:
        judgment = await _judge_answerability(search_query, results)

    # 6. Build evidence packet
    packet = _build_evidence_packet(
        query=query,
        results=results,
        judgment=judgment,
        rewrite=rewrite,
        fusion_context=fusion_context[:5],
        graph_context=graph_context[:5],
        start_time=_t0,
    )

    return {
        "evidence_packet": {
            "query": packet.query,
            "answerable": packet.answerable,
            "answerability_reason": packet.answerability_reason,
            "citations": [
                {
                    "chunk_id": c.chunk_id,
                    "document_id": c.document_id,
                    "page": c.page,
                    "text": c.text,
                    "score": c.score,
                    "source": c.source,
                    "provenance": c.provenance,
                }
                for c in packet.citations
            ],
            "citation_count": packet.citation_count,
            "fusion_context": packet.fusion_context,
            "graph_context": packet.graph_context,
            "rewritten_query": packet.rewritten_query,
            "confidence": packet.confidence,
            "timing_ms": packet.timing_ms,
        },
        "raw_results": results,
    }


# ── Unit-testable helpers ────────────────────────────────────────────────


def build_evidence_packet_sync(
    query: str,
    results: list[dict],
    judgment: AnswerabilityJudgment,
    rewrite: QueryRewriteResult | None = None,
    fusion_context: list[dict] | None = None,
    graph_context: list[dict] | None = None,
) -> EvidencePacket:
    """Synchronous builder for testing."""
    return _build_evidence_packet(query, results, judgment, rewrite, fusion_context, graph_context)


async def get_document_chunks(db: AsyncSession, document_id: int) -> list[dict]:
    """获取某文档的所有内容块（按页和块索引排序）。"""
    from ..models import KbChunk

    stmt = (
        select(KbChunk)
        .where(KbChunk.document_id == document_id)
        .order_by(KbChunk.page, KbChunk.chunk_index)
    )
    r = await db.execute(stmt)
    chunks = r.scalars().all()
    return [
        {
            "id": ch.id,
            "document_id": ch.document_id,
            "page": ch.page,
            "chunk_index": ch.chunk_index,
            "block_type": ch.block_type,
            "text": ch.text,
            "keywords": ch.keywords,
        }
        for ch in chunks
    ]
