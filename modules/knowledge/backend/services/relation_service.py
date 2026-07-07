"""第7层 跨文件动态关联服务（★华哥最看重）。

新文件入库 → 自动跟已有文件建立关联边：文件画像向量相似度 + 实体共现度 → kb_file_relations。
增量计算：只算新文件与已有文件的关联，不全量重算。
逐边 commit，幂等可重入（已有边跳过，中断只丢当前边）。
"""
import logging
from time import perf_counter

from app.database import AsyncSessionLocal
from sqlalchemy import desc, distinct, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import KbChunkEntity, KbDocument, KbDocumentProfile, KbEntityDictionary, KbFileRelation
from .model_routing import resolve_knowledge_concurrency
from .profile_vector_service import ensure_document_profile_vector, vector_literal

logger = logging.getLogger("v2.knowledge").getChild("relation")

VECTOR_CANDIDATE_LIMIT = 2000
ENTITY_CANDIDATE_LIMIT = 1000
RELATION_WRITE_BATCH = 100


def _cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """余弦相似度。"""
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = sum(a * a for a in vec_a) ** 0.5
    norm_b = sum(b * b for b in vec_b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


async def _get_document_entity_ids(db: AsyncSession, document_id: int) -> set[int]:
    """获取文档关联的实体 ID 集合。"""
    r = await db.execute(
        select(KbChunkEntity.entity_id).where(KbChunkEntity.document_id == document_id)
    )
    return {row[0] for row in r.all()}


def _entity_overlap_score(entities_a: set[int], entities_b: set[int]) -> float:
    """实体共现 Jaccard 相似度。"""
    if not entities_a or not entities_b:
        return 0.0
    intersection = len(entities_a & entities_b)
    union = len(entities_a | entities_b)
    return intersection / union if union > 0 else 0.0


def _batched(items: list[dict], batch_size: int) -> list[list[dict]]:
    return [items[index:index + batch_size] for index in range(0, len(items), batch_size)]


async def compute_file_relations(
    db: AsyncSession,
    document_id: int,
    owner_id: int,
) -> dict:
    """为新文件计算与已有文件的关联边（增量，逐边 commit，幂等可重入）。

    基于：文件画像向量余弦相似度(0.6权重) + 实体共现 Jaccard(0.4权重)。
    已有边（同 source/target）跳过，中断只丢当前边。
    """
    stage_started = perf_counter()
    # Release any outer transaction before the potentially large relation pass.
    # This stage reads a snapshot, computes in memory, then writes edges in short
    # transactions so worker lanes do not pin DB connections while scoring.
    await db.commit()

    snapshot_started = perf_counter()
    async with AsyncSessionLocal() as read_db:
        new_embedding = await ensure_document_profile_vector(
            read_db,
            owner_id=owner_id,
            document_id=document_id,
        )
        if not new_embedding:
            await read_db.commit()
            logger.warning("No profile/embedding for document_id=%d, skipping relations", document_id)
            return {
                "document_id": document_id,
                "relations_created": 0,
                "timing": {
                    "stage_wall_ms": round((perf_counter() - stage_started) * 1000),
                    "snapshot_ms": round((perf_counter() - snapshot_started) * 1000),
                    "candidate_documents": 0,
                    "relations_created": 0,
                    "reason": "missing_profile_embedding",
                },
            }

        r = await read_db.execute(
            select(KbFileRelation.source_document_id, KbFileRelation.target_document_id)
            .where(
                KbFileRelation.owner_id == owner_id,
                (
                    (KbFileRelation.source_document_id == document_id)
                    | (KbFileRelation.target_document_id == document_id)
                ),
            )
        )
        existing_edges = {(row[0], row[1]) for row in r.all()}
        await read_db.commit()

    async with AsyncSessionLocal() as current_entity_db:
        current_entity_result = await current_entity_db.execute(
            select(KbChunkEntity.entity_id).where(
                KbChunkEntity.owner_id == owner_id,
                KbChunkEntity.document_id == document_id,
            )
        )
        new_entities = {int(row[0]) for row in current_entity_result.all()}
        await current_entity_db.commit()
    snapshot_duration_ms = round((perf_counter() - snapshot_started) * 1000)

    if not new_embedding:
        logger.warning("No profile/embedding for document_id=%d, skipping relations", document_id)
        return {
            "document_id": document_id,
            "relations_created": 0,
            "timing": {
                "stage_wall_ms": round((perf_counter() - stage_started) * 1000),
                "snapshot_ms": snapshot_duration_ms,
                "candidate_documents": 0,
                "relations_created": 0,
                "reason": "missing_profile_embedding",
            },
        }

    candidate_started = perf_counter()
    vector_candidate_limit = resolve_knowledge_concurrency(
        "relation_vector_candidates",
        VECTOR_CANDIDATE_LIMIT,
        minimum=100,
        maximum=10000,
    )
    entity_candidate_limit = resolve_knowledge_concurrency(
        "relation_entity_candidates",
        ENTITY_CANDIDATE_LIMIT,
        minimum=100,
        maximum=10000,
    )
    vector_candidate_scores: dict[int, float] = {}
    async with AsyncSessionLocal() as candidate_db:
        vector_result = await candidate_db.execute(
            text(
                """
                SELECT document_id, 1 - (embedding <=> CAST(:embedding AS vector)) AS vector_score
                FROM kb_document_profile_vectors
                WHERE owner_id = :owner_id
                  AND status = 'active'
                  AND document_id != :document_id
                ORDER BY embedding <=> CAST(:embedding AS vector)
                LIMIT :limit
                """
            ),
            {
                "owner_id": owner_id,
                "document_id": document_id,
                "embedding": vector_literal(new_embedding),
                "limit": vector_candidate_limit,
            },
        )
        vector_candidate_scores = {
            int(row[0]): float(row[1] or 0.0)
            for row in vector_result.all()
        }
        await candidate_db.commit()

    entity_candidate_ids: set[int] = set()
    if new_entities:
        async with AsyncSessionLocal() as entity_candidate_db:
            entity_candidate_result = await entity_candidate_db.execute(
                select(
                    KbChunkEntity.document_id,
                    func.count(distinct(KbChunkEntity.entity_id)).label("shared_count"),
                )
                .where(
                    KbChunkEntity.owner_id == owner_id,
                    KbChunkEntity.document_id != document_id,
                    KbChunkEntity.entity_id.in_(list(new_entities)),
                )
                .group_by(KbChunkEntity.document_id)
                .order_by(desc("shared_count"))
                .limit(entity_candidate_limit)
            )
            entity_candidate_ids = {int(row[0]) for row in entity_candidate_result.all()}
            await entity_candidate_db.commit()

    candidate_ids = sorted(set(vector_candidate_scores) | entity_candidate_ids)
    candidate_duration_ms = round((perf_counter() - candidate_started) * 1000)

    existing_profiles: list[tuple[int, list[float]]] = []
    if candidate_ids:
        async with AsyncSessionLocal() as profile_db:
            profile_result = await profile_db.execute(
                select(KbDocumentProfile.document_id, KbDocumentProfile.profile_embedding).where(
                    KbDocumentProfile.owner_id == owner_id,
                    KbDocumentProfile.document_id.in_(candidate_ids),
                    KbDocumentProfile.profile_embedding.isnot(None),
                )
            )
            existing_profiles = [
                (int(row[0]), list(row[1] or []))
                for row in profile_result.all()
                if row[1]
            ]
            await profile_db.commit()

    async with AsyncSessionLocal() as entity_db:
        entity_rows = []
        if candidate_ids:
            entity_result = await entity_db.execute(
                select(KbChunkEntity.document_id, KbChunkEntity.entity_id).where(
                    KbChunkEntity.owner_id == owner_id,
                    KbChunkEntity.document_id.in_([document_id, *candidate_ids]),
                )
            )
            entity_rows = entity_result.all()
        else:
            entity_result = await entity_db.execute(
                select(KbChunkEntity.document_id, KbChunkEntity.entity_id).where(
                    KbChunkEntity.owner_id == owner_id,
                    KbChunkEntity.document_id == document_id,
                )
            )
            entity_rows = entity_result.all()
        await entity_db.commit()

    doc_entities: dict[int, set[int]] = {}
    for row_doc_id, row_entity_id in entity_rows:
        doc_entities.setdefault(int(row_doc_id), set()).add(int(row_entity_id))
    new_entities = doc_entities.get(document_id, set())

    relations_created = 0
    scored_documents = 0
    skipped_existing_edges = 0
    below_threshold = 0
    db_commit_duration_ms = 0
    score_duration_ms = 0
    write_batches = 0
    planned_relations: list[dict] = []
    all_shared_entity_ids: set[int] = set()
    score_started = perf_counter()
    for existing_document_id, existing_embedding in existing_profiles:
        if not existing_embedding:
            continue

        # 幂等：双向边成对创建,正向已存在即跳过整对
        fwd_edge = (document_id, existing_document_id)
        rev_edge = (existing_document_id, document_id)
        if fwd_edge in existing_edges or rev_edge in existing_edges:
            skipped_existing_edges += 1
            continue

        # 向量相似度
        vec_sim = _cosine_similarity(new_embedding, existing_embedding)

        # 实体共现度
        existing_entities = doc_entities.get(int(existing_document_id), set())
        entity_sim = _entity_overlap_score(new_entities, existing_entities)

        # 综合分数（向量 0.6 + 实体 0.4）
        combined_score = round(vec_sim * 0.6 + entity_sim * 0.4, 4)
        scored_documents += 1

        # 阈值：综合 >0.15 才建边
        if combined_score < 0.15:
            below_threshold += 1
            continue

        # 确定关系类型
        if entity_sim > 0.3:
            relation_type = "entity_overlap"
        elif vec_sim > 0.8:
            relation_type = "semantic_similar"
        else:
            relation_type = "reference"

        common_entities = list(new_entities & existing_entities)[:10] if new_entities and existing_entities else []
        all_shared_entity_ids.update(common_entities)
        planned_relations.append({
            "target_document_id": int(existing_document_id),
            "relation_type": relation_type,
            "combined_score": combined_score,
            "vec_sim": vec_sim,
            "entity_sim": entity_sim,
            "shared_entity_ids": common_entities,
        })
    score_duration_ms = round((perf_counter() - score_started) * 1000)

    entity_names: dict[int, str] = {}
    if all_shared_entity_ids:
        name_started = perf_counter()
        async with AsyncSessionLocal() as name_db:
            ent_r = await name_db.execute(
                select(KbEntityDictionary.id, KbEntityDictionary.name).where(
                    KbEntityDictionary.owner_id == owner_id,
                    KbEntityDictionary.id.in_(list(all_shared_entity_ids)),
                )
            )
            entity_names = {int(row[0]): str(row[1]) for row in ent_r.all()}
            await name_db.commit()
        db_commit_duration_ms += round((perf_counter() - name_started) * 1000)

    relation_write_batch = resolve_knowledge_concurrency(
        "relation_write_batch",
        RELATION_WRITE_BATCH,
        minimum=1,
        maximum=1000,
    )
    for planned_batch in _batched(planned_relations, relation_write_batch):
        target_ids = [int(planned["target_document_id"]) for planned in planned_batch]
        write_started = perf_counter()
        try:
            async with AsyncSessionLocal() as write_db:
                edge_check = await write_db.execute(
                    select(KbFileRelation.source_document_id, KbFileRelation.target_document_id).where(
                        KbFileRelation.owner_id == owner_id,
                        (
                            (
                                (KbFileRelation.source_document_id == document_id)
                                & (KbFileRelation.target_document_id.in_(target_ids))
                            )
                            | (
                                (KbFileRelation.target_document_id == document_id)
                                & (KbFileRelation.source_document_id.in_(target_ids))
                            )
                        ),
                    )
                )
                existing_target_ids: set[int] = set()
                for src_id, tgt_id in edge_check.all():
                    if int(src_id) == document_id:
                        existing_target_ids.add(int(tgt_id))
                    elif int(tgt_id) == document_id:
                        existing_target_ids.add(int(src_id))

                for planned in planned_batch:
                    existing_document_id = int(planned["target_document_id"])
                    if existing_document_id in existing_target_ids:
                        skipped_existing_edges += 1
                        continue
                    shared_entity_names = [
                        entity_names[entity_id]
                        for entity_id in planned["shared_entity_ids"]
                        if entity_id in entity_names
                    ]
                    for src_id, tgt_id in [(document_id, existing_document_id), (existing_document_id, document_id)]:
                        relation = KbFileRelation(
                            owner_id=owner_id,
                            source_document_id=src_id,
                            target_document_id=tgt_id,
                            relation_type=planned["relation_type"],
                            similarity_score=planned["combined_score"],
                            shared_entities=shared_entity_names if src_id == document_id else None,
                            evidence=(
                                f"向量相似度={planned['vec_sim']:.3f}, 实体共现={planned['entity_sim']:.3f}"
                                if src_id == document_id else None
                            ),
                            weight=planned["combined_score"],
                        )
                        write_db.add(relation)
                        relations_created += 1
                await write_db.commit()
                write_batches += 1
        except Exception:
            raise
        finally:
            db_commit_duration_ms += round((perf_counter() - write_started) * 1000)

    logger.info("Created %d file relations for document_id=%d", relations_created, document_id)
    return {
        "document_id": document_id,
        "relations_created": relations_created,
        "timing": {
            "stage_wall_ms": round((perf_counter() - stage_started) * 1000),
            "snapshot_ms": snapshot_duration_ms,
            "candidate_ms": candidate_duration_ms,
            "score_ms": score_duration_ms,
            "candidate_documents": len(existing_profiles),
            "vector_candidates": len(vector_candidate_scores),
            "entity_candidates": len(entity_candidate_ids),
            "merged_candidates": len(candidate_ids),
            "vector_candidate_limit": vector_candidate_limit,
            "entity_candidate_limit": entity_candidate_limit,
            "scored_documents": scored_documents,
            "skipped_existing_edges": skipped_existing_edges,
            "below_threshold": below_threshold,
            "relations_created": relations_created,
            "relation_write_batch": relation_write_batch,
            "write_batches": write_batches,
            "db_commit_ms": db_commit_duration_ms,
        },
    }


async def get_file_relations(
    db: AsyncSession, document_id: int,
) -> list[dict]:
    """查询文件的关联边列表。"""
    r = await db.execute(
        select(KbFileRelation).where(KbFileRelation.source_document_id == document_id)
        .order_by(KbFileRelation.similarity_score.desc())
        .limit(50)
    )
    relations = r.scalars().all()

    # 补充目标文件名
    target_ids = list({rel.target_document_id for rel in relations})
    doc_names: dict[int, str] = {}
    if target_ids:
        doc_r = await db.execute(
            select(KbDocument.id, KbDocument.filename).where(KbDocument.id.in_(target_ids))
        )
        doc_names = {row[0]: row[1] for row in doc_r.all()}

    return [
        {
            "id": rel.id,
            "source_document_id": rel.source_document_id,
            "target_document_id": rel.target_document_id,
            "target_filename": doc_names.get(rel.target_document_id, ""),
            "relation_type": rel.relation_type,
            "similarity_score": rel.similarity_score,
            "shared_entities": rel.shared_entities,
            "evidence": rel.evidence,
            "weight": rel.weight,
            "created_at": rel.created_at.isoformat() if rel.created_at else None,
        }
        for rel in relations
    ]


async def get_relation_graph(db: AsyncSession, owner_id: int) -> dict:
    """获取知识网络全景（所有文件关联边的图结构）。"""
    r = await db.execute(
        select(KbFileRelation).where(KbFileRelation.owner_id == owner_id)
        .order_by(KbFileRelation.similarity_score.desc())
        .limit(200)
    )
    relations = r.scalars().all()

    # 收集文件
    doc_ids = set()
    for rel in relations:
        doc_ids.add(rel.source_document_id)
        doc_ids.add(rel.target_document_id)

    doc_r = await db.execute(
        select(KbDocument.id, KbDocument.filename).where(KbDocument.id.in_(doc_ids))
    )
    doc_names = {row[0]: row[1] for row in doc_r.all()}

    nodes = [{"id": did, "label": doc_names.get(did, f"Doc#{did}"), "type": "document"} for did in doc_ids]
    edges = [
        {
            "source": rel.source_document_id,
            "target": rel.target_document_id,
            "relation_type": rel.relation_type,
            "weight": rel.weight,
        }
        for rel in relations
    ]

    return {"nodes": nodes, "edges": edges}
