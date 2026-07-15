# -*- coding: utf-8 -*-
"""验证实体锚定改动:entities是否填充 + 召回精度是否提升。owner_id=4。"""
import asyncio, sys
sys.path.insert(0, "backend"); sys.path.insert(0, ".")
from app.database import AsyncSessionLocal
from modules.knowledge.backend.services.search_service import plan_query, hybrid_search

OWNER = 4
QUERIES = [
    "积雪草苷对敏感肌的功效和推荐浓度",
    "俏小喵有哪些主打修护的产品",
    "烟酰胺的美白原理",
]

async def main():
    async with AsyncSessionLocal() as db:
        for q in QUERIES:
            print(f"\n{'#'*72}\n查询: {q}")
            plan = await plan_query(q, db=db, owner_id=OWNER)
            print(f"  source={plan.get('source')}  entities={plan.get('entities')}")
            print(f"  terms={plan.get('terms')[:8]}")
            results = await hybrid_search(db, q, OWNER, top_k=5)
            print(f"  --- top5 ---")
            for i, r in enumerate(results[:5]):
                txt = (r.get('text') or '').replace('\n',' ')[:70]
                print(f"  {i+1}. [{r.get('index_layer')}] score={r.get('score',0):.3f} vec={r.get('vec_score',0):.2f} struct={r.get('structured_score',0):.2f}")
                print(f"      {txt}")

if __name__ == "__main__":
    asyncio.run(main())
