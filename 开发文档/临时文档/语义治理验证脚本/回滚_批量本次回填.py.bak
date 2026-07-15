# -*- coding: utf-8 -*-
"""批量回滚本次回填的所有合并(按 merge_log,reason='文本层打齐%',近2小时)。owner=4。
撤销:chunk_entities/evidence/graph_nodes 从锚点撤回变体、删alias、恢复变体字典、删semantic_align新建的锚点、删日志。"""
import asyncio, sys
sys.path.insert(0, "backend"); sys.path.insert(0, ".")
from app.database import AsyncSessionLocal
from sqlalchemy import text as T

OWNER = 4

async def m():
    async with AsyncSessionLocal() as db:
        r = await db.execute(T("""
            SELECT id, source_entity_ids, target_entity_id, reason FROM kb_entity_merge_log
            WHERE owner_id=:o AND reason LIKE '文本层打齐%' AND created_at > now() - interval '3 hours'
            ORDER BY id
        """), {"o": OWNER})
        rows = r.all()
        print(f"待回滚合并: {len(rows)}")
        for log_id, src_ids, anchor_id, reason in rows:
            variant_ids = src_ids if isinstance(src_ids, list) else []
            for vid in variant_ids:
                # 取变体原名(从字典;已被标merged但name还在)
                nr = await db.execute(T("SELECT name FROM kb_entity_dictionary WHERE id=:v AND owner_id=:o"), {"v": vid, "o": OWNER})
                row = nr.first()
                vname = row[0] if row else None
                # chunk_entities/evidence/graph 从锚点撤回变体
                await db.execute(T("UPDATE kb_chunk_entities SET entity_id=:v WHERE entity_id=:a AND owner_id=:o AND entity_id!=:v"), {"v": vid, "a": anchor_id, "o": OWNER})
                await db.execute(T("UPDATE kb_evidence SET entity_id=:v WHERE entity_id=:a AND owner_id=:o AND entity_id!=:v"), {"v": vid, "a": anchor_id, "o": OWNER})
                if vname:
                    await db.execute(T("UPDATE kb_graph_nodes SET entity_id=:v, label=:n WHERE entity_id=:a AND owner_id=:o"), {"v": vid, "n": vname, "a": anchor_id, "o": OWNER})
                    await db.execute(T("DELETE FROM kb_entity_aliases WHERE owner_id=:o AND entity_id=:a AND alias=:n"), {"o": OWNER, "a": anchor_id, "n": vname})
                # 恢复变体字典
                await db.execute(T("UPDATE kb_entity_dictionary SET status='candidate', canonical_id=NULL, semantic_meta=NULL, align_status='pending' WHERE id=:v AND owner_id=:o"), {"v": vid, "o": OWNER})
            # 删 semantic_align 新建的锚点(仅当无其他引用且是本引擎建的)
            ref = await db.execute(T("SELECT count(*) FROM kb_chunk_entities WHERE entity_id=:a AND owner_id=:o"), {"a": anchor_id, "o": OWNER})
            if ref.first()[0] == 0:
                await db.execute(T("DELETE FROM kb_entity_dictionary WHERE id=:a AND owner_id=:o AND source='semantic_align'"), {"a": anchor_id, "o": OWNER})
            await db.execute(T("DELETE FROM kb_entity_merge_log WHERE id=:i"), {"i": log_id})
            print(f"  回滚: {reason}")
        await db.commit()
        # 把本次打了 done 的实体重置回 pending(下次修好算法重跑)
        rr = await db.execute(T("UPDATE kb_entity_dictionary SET align_status='pending' WHERE owner_id=:o AND align_status='done'"), {"o": OWNER})
        await db.commit()
        print("已把 align_status=done 全部重置回 pending(等算法修好重跑)")

if __name__ == "__main__":
    asyncio.run(m())
