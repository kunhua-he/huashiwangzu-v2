# -*- coding: utf-8 -*-
"""P1验证:本地LLM双层拆词。通道+碎片纠正+泛词归高层。owner_id=4。"""
import asyncio, sys, time
sys.path.insert(0, "backend"); sys.path.insert(0, ".")
from app.database import AsyncSessionLocal
from modules.knowledge.backend.services.search_service import plan_query

OWNER = 4
# 都是≥25字的长/混沌查询,触发LLM双层拆词
QUERIES = [
    "我想了解积雪草苷这个成分对敏感肌肤到底有没有修护功效以及日常使用推荐浓度是多少",
    "烟酰胺和视黄醇能不能一起用会不会刺激烂脸有没有什么搭配禁忌需要注意的",
    "帮我找找店里针对痘痘肌和闭口粉刺的祛痘产品都有哪些以及怎么搭配使用效果最好",
]

async def main():
    async with AsyncSessionLocal() as db:
        for q in QUERIES:
            print(f"\n{'#'*72}\n查询({len(q)}字): {q}")
            t0 = time.perf_counter()
            plan = await plan_query(q, db=db, owner_id=OWNER)
            dt = round((time.perf_counter()-t0)*1000)
            print(f"  source={plan.get('source')}  耗时={dt}ms")
            core = plan.get('core_entities') or []
            print(f"  core_entities(低层实体,LLM定性+IDF定权):")
            for c in core:
                print(f"    {c['name']:<16} 权重={c['weight']:<7} df={c['df']:<5} {c['category']}")
            print(f"  concept_terms(高层概念)={plan.get('concept_terms')}")

if __name__ == "__main__":
    asyncio.run(main())
