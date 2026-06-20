"""
一次性清理脚本：消除知识库模块中由旧版 buggy pipeline 产生的历史重复数据。

清理范围：
1. kb_entity_dictionary：同 (owner_id, name) 只保留 id 最小的那条，重定向所有引用后删除多余行
2. kb_graph_nodes：同 entity_id 去重（保留一个），边的引用一并修正
3. kb_governance_candidates：同 (document_id, entity_name) 只保留一条

全程事务安全、可重入。执行完后本脚本可安全删除。
"""
import asyncio
import logging
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../backend"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))

from sqlalchemy import select, delete as sa_delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal

logger = logging.getLogger("v2.knowledge.cleanup_dupes")


async def _get_models():
    """延迟导入模块模型。"""
    from modules.knowledge.backend.models import (
        KbEntityDictionary, KbGraphNode, KbGraphEdge,
        KbChunkEntity, KbEvidence, KbGovernanceCandidate,
    )
    return {
        "KbEntityDictionary": KbEntityDictionary,
        "KbGraphNode": KbGraphNode,
        "KbGraphEdge": KbGraphEdge,
        "KbChunkEntity": KbChunkEntity,
        "KbEvidence": KbEvidence,
        "KbGovernanceCandidate": KbGovernanceCandidate,
    }


async def cleanup_entity_dictionary_dupes(db: AsyncSession) -> dict:
    """清理 kb_entity_dictionary 中同 (owner_id, name) 的重复记录。

    策略：对每个 (owner_id, name) 分组，保留 id 最小的为"幸存者"，
    把其他表的引用重定向到幸存者，再删除重复行。
    """
    M = await _get_models()
    KbEntityDictionary = M["KbEntityDictionary"]
    KbGraphNode = M["KbGraphNode"]
    KbChunkEntity = M["KbChunkEntity"]
    KbEvidence = M["KbEvidence"]

    # 查出所有重复组
    r = await db.execute(
        select(KbEntityDictionary.owner_id, KbEntityDictionary.name,
               func.count(KbEntityDictionary.id).label("cnt"))
        .group_by(KbEntityDictionary.owner_id, KbEntityDictionary.name)
        .having(func.count(KbEntityDictionary.id) > 1)
    )
    dup_groups = list(r.all())
    deleted_count = 0

    for owner_id, name, cnt in dup_groups:
        r = await db.execute(
            select(KbEntityDictionary)
            .where(KbEntityDictionary.owner_id == owner_id,
                   KbEntityDictionary.name == name)
            .order_by(KbEntityDictionary.id)
        )
        rows = list(r.scalars().all())
        if len(rows) <= 1:
            continue

        survivor = rows[0]
        dupes = rows[1:]
        dupe_ids = [d.id for d in dupes]

        # 删除引用了重复实体 ID 的图谱节点（连带边在 cleanup_graph_nodes 处理）
        await db.execute(
            sa_delete(KbGraphNode).where(
                KbGraphNode.entity_id.in_(dupe_ids)
            )
        )
        # 删除 chunk-entity 关联
        await db.execute(
            sa_delete(KbChunkEntity).where(
                KbChunkEntity.entity_id.in_(dupe_ids)
            )
        )
        # 删除证据
        await db.execute(
            sa_delete(KbEvidence).where(
                KbEvidence.entity_id.in_(dupe_ids)
            )
        )

        # 删除重复的实体词典条目
        for d in dupes:
            await db.delete(d)
            deleted_count += 1

        logger.info("  Merged %d dupes for (owner=%d, name='%s') → survivor id=%d",
                     len(dupes), owner_id, name, survivor.id)

    await db.commit()
    logger.info("EntityDictionary: cleaned %d duplicate rows across %d groups",
                deleted_count, len(dup_groups))
    return {"groups": len(dup_groups), "deleted": deleted_count}


async def cleanup_graph_nodes_dupes(db: AsyncSession) -> dict:
    """清理 kb_graph_nodes 中同 entity_id 的重复节点。

    策略：对每个 entity_id 分组，保留 id 最小的节点；
    删除引用重复节点 ID 的边和重复节点本身。
    """
    M = await _get_models()
    KbGraphNode = M["KbGraphNode"]
    KbGraphEdge = M["KbGraphEdge"]

    r = await db.execute(
        select(KbGraphNode.entity_id,
               func.count(KbGraphNode.id).label("cnt"))
        .group_by(KbGraphNode.entity_id)
        .having(func.count(KbGraphNode.id) > 1)
    )
    dup_groups = list(r.all())
    deleted_count = 0

    for entity_id, cnt in dup_groups:
        r = await db.execute(
            select(KbGraphNode)
            .where(KbGraphNode.entity_id == entity_id)
            .order_by(KbGraphNode.id)
        )
        nodes = list(r.scalars().all())
        if len(nodes) <= 1:
            continue

        dupe_node_ids = [n.id for n in nodes[1:]]

        # 删除引用这些重复 node 的边
        if dupe_node_ids:
            await db.execute(
                sa_delete(KbGraphEdge).where(
                    (KbGraphEdge.source_node_id.in_(dupe_node_ids))
                    | (KbGraphEdge.target_node_id.in_(dupe_node_ids))
                )
            )

        # 删除重复节点
        for n in nodes[1:]:
            await db.delete(n)
            deleted_count += 1

        logger.info("  Merged %d graph node dupes for entity_id=%d → survivor id=%d",
                     len(nodes) - 1, entity_id, nodes[0].id)

    await db.commit()
    logger.info("GraphNodes: cleaned %d duplicate rows across %d groups",
                deleted_count, len(dup_groups))
    return {"groups": len(dup_groups), "deleted": deleted_count}


async def cleanup_governance_candidates_dupes(db: AsyncSession) -> dict:
    """清理 kb_governance_candidates 中同 (document_id, entity_name) 的重复。"""
    M = await _get_models()
    KbGovernanceCandidate = M["KbGovernanceCandidate"]

    r = await db.execute(
        select(KbGovernanceCandidate.document_id, KbGovernanceCandidate.entity_name,
               func.count(KbGovernanceCandidate.id).label("cnt"))
        .group_by(KbGovernanceCandidate.document_id, KbGovernanceCandidate.entity_name)
        .having(func.count(KbGovernanceCandidate.id) > 1)
    )
    dup_groups = list(r.all())
    deleted_count = 0

    for doc_id, name, cnt in dup_groups:
        r = await db.execute(
            select(KbGovernanceCandidate)
            .where(KbGovernanceCandidate.document_id == doc_id,
                   KbGovernanceCandidate.entity_name == name)
            .order_by(KbGovernanceCandidate.id)
        )
        rows = list(r.scalars().all())
        if len(rows) <= 1:
            continue

        for d in rows[1:]:
            await db.delete(d)
            deleted_count += 1

        logger.info("  Cleaned %d candidate dupes for (doc=%d, name='%s')",
                     len(rows) - 1, doc_id, name)

    await db.commit()
    logger.info("GovernanceCandidates: cleaned %d duplicate rows across %d groups",
                deleted_count, len(dup_groups))
    return {"groups": len(dup_groups), "deleted": deleted_count}


async def run_cleanup(db: AsyncSession) -> dict:
    """运行全量清理，返回统计。"""
    results = {}
    results["entity_dictionary"] = await cleanup_entity_dictionary_dupes(db)
    results["graph_nodes"] = await cleanup_graph_nodes_dupes(db)
    results["governance_candidates"] = await cleanup_governance_candidates_dupes(db)
    return results


async def verify_cleanup(db: AsyncSession) -> dict:
    """验证三类表是否还有重复，返回统计。"""
    M = await _get_models()
    KbEntityDictionary = M["KbEntityDictionary"]
    KbGraphNode = M["KbGraphNode"]
    KbGovernanceCandidate = M["KbGovernanceCandidate"]

    # kb_entity_dictionary: 同 (owner_id, name) 重复组数
    r = await db.execute(
        select(func.count())
        .select_from(
            select(KbEntityDictionary.owner_id, KbEntityDictionary.name,
                   func.count(KbEntityDictionary.id).label("cnt"))
            .group_by(KbEntityDictionary.owner_id, KbEntityDictionary.name)
            .having(func.count(KbEntityDictionary.id) > 1)
            .subquery()
        )
    )
    ent_dupes = r.scalar() or 0

    # kb_graph_nodes: 同 entity_id 重复组数
    r = await db.execute(
        select(func.count())
        .select_from(
            select(KbGraphNode.entity_id,
                   func.count(KbGraphNode.id).label("cnt"))
            .group_by(KbGraphNode.entity_id)
            .having(func.count(KbGraphNode.id) > 1)
            .subquery()
        )
    )
    node_dupes = r.scalar() or 0

    # kb_governance_candidates: 同 (document_id, entity_name) 重复组数
    r = await db.execute(
        select(func.count())
        .select_from(
            select(KbGovernanceCandidate.document_id, KbGovernanceCandidate.entity_name,
                   func.count(KbGovernanceCandidate.id).label("cnt"))
            .group_by(KbGovernanceCandidate.document_id, KbGovernanceCandidate.entity_name)
            .having(func.count(KbGovernanceCandidate.id) > 1)
            .subquery()
        )
    )
    cand_dupes = r.scalar() or 0

    result = {
        "entity_dictionary_dupe_groups": ent_dupes,
        "graph_nodes_dupe_groups": node_dupes,
        "governance_candidates_dupe_groups": cand_dupes,
    }
    logger.info("Verify dupes: %s", result)
    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(name)s] %(levelname)s [-] %(message)s")

    async def main():
        async with AsyncSessionLocal() as db:
            print("=" * 60)
            print("BEFORE cleanup:")
            before = await verify_cleanup(db)
            for k, v in before.items():
                print(f"  {k}: {v}")

            print()
            print("Running cleanup...")
            results = await run_cleanup(db)
            for k, v in results.items():
                print(f"  {k}: deleted={v.get('deleted', 0)}, groups={v.get('groups', 0)}")

            print()
            print("AFTER cleanup:")
            after = await verify_cleanup(db)
            for k, v in after.items():
                print(f"  {k}: {v}")

            all_clean = all(v == 0 for v in after.values())
            print()
            print(f"All clean: {all_clean}")
            return all_clean

    ok = asyncio.run(main())
    sys.exit(0 if ok else 1)
