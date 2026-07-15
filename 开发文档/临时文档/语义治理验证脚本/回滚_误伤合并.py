# -*- coding: utf-8 -*-
"""回滚单个误伤合并:把变体从锚点撤回。owner_id=4。
用法: python 回滚_误伤合并.py <变体entity_id> <误建锚点entity_id> <原变体名>"""
import asyncio, sys
sys.path.insert(0, "backend"); sys.path.insert(0, ".")
from app.database import AsyncSessionLocal
from sqlalchemy import text as T

async def rollback(variant_id, wrong_anchor_id, variant_name):
    async with AsyncSessionLocal() as db:
        o=4
        # chunk_entities / evidence / graph_nodes 从误锚点撤回变体
        await db.execute(T("UPDATE kb_chunk_entities SET entity_id=:v WHERE entity_id=:a AND owner_id=:o"),{"v":variant_id,"a":wrong_anchor_id,"o":o})
        await db.execute(T("UPDATE kb_evidence SET entity_id=:v WHERE entity_id=:a AND owner_id=:o"),{"v":variant_id,"a":wrong_anchor_id,"o":o})
        await db.execute(T("UPDATE kb_graph_nodes SET entity_id=:v, label=:n WHERE entity_id=:a AND owner_id=:o"),{"v":variant_id,"n":variant_name,"a":wrong_anchor_id,"o":o})
        # 删别名、恢复变体字典、删误锚点、删合并日志
        await db.execute(T("DELETE FROM kb_entity_aliases WHERE owner_id=:o AND entity_id=:a AND alias=:n"),{"o":o,"a":wrong_anchor_id,"n":variant_name})
        await db.execute(T("UPDATE kb_entity_dictionary SET status='candidate', canonical_id=NULL, semantic_meta=NULL WHERE id=:v AND owner_id=:o"),{"v":variant_id,"o":o})
        await db.execute(T("DELETE FROM kb_entity_dictionary WHERE id=:a AND owner_id=:o AND source='semantic_align'"),{"a":wrong_anchor_id,"o":o})
        await db.execute(T("DELETE FROM kb_entity_merge_log WHERE owner_id=:o AND target_entity_id=:a"),{"o":o,"a":wrong_anchor_id})
        await db.commit()
        print(f"已回滚: 变体{variant_id}({variant_name}) 从误锚点{wrong_anchor_id}撤回")

if __name__=="__main__":
    asyncio.run(rollback(int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]))
