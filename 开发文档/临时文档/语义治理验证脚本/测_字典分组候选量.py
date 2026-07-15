# -*- coding: utf-8 -*-
"""纯Python字典分组:同类别同长度、只差一个字位的实体=变体家族。不碰语料,秒级。owner=4。"""
import asyncio, sys, time
from collections import defaultdict
sys.path.insert(0, "backend"); sys.path.insert(0, ".")
from app.database import AsyncSessionLocal
from sqlalchemy import text as T

async def m():
    t = time.time()
    async with AsyncSessionLocal() as db:
        r = await db.execute(T("""
            SELECT DISTINCT ed.id, ed.name, ed.category
            FROM kb_chunk_entities ce JOIN kb_entity_dictionary ed ON ed.id=ce.entity_id AND ed.owner_id=ce.owner_id
            WHERE ce.owner_id=4 AND ed.status!='merged' AND ed.name ~ '[一-鿿]' AND length(ed.name) BETWEEN 3 AND 24
        """))
        ents = [(int(i), n, c) for i, n, c in r.all()]
    print(f"加载 {len(ents)} 实体, 耗时{time.time()-t:.1f}s")
    # 按 (类别,长度) 分桶,桶内用"遮一位"的键分组
    masked = defaultdict(list)  # (category, len, pos, masked_str) -> [id...]
    for eid, name, cat in ents:
        L = len(name)
        for i in range(L):
            key = (cat, L, i, name[:i] + "\0" + name[i+1:])
            masked[key].append(eid)
    variant_ids = set()
    group_cnt = 0
    for key, ids in masked.items():
        if len(ids) >= 2:  # 同一遮位键有≥2个 = 差一字家族
            group_cnt += 1
            variant_ids.update(ids)
    print(f"变体家族数: {group_cnt}, 涉及实体: {len(variant_ids)}, 总耗时{time.time()-t:.1f}s")

if __name__ == "__main__":
    asyncio.run(m())
