# -*- coding: utf-8 -*-
"""P1验证:查询理解层IDF定权。core_entities是否带正确权重,专名>泛词。owner_id=4。"""
import asyncio, sys
sys.path.insert(0, "backend"); sys.path.insert(0, ".")
from app.database import AsyncSessionLocal
from modules.knowledge.backend.services.search_service import plan_query

OWNER = 4
QUERIES = [
    "积雪草苷对敏感肌的功效和推荐浓度",
    "烟酰胺的美白原理",
    "俏小喵有哪些主打修护的产品",
    "早C晚A怎么搭配不烂脸",
    "价目表",
]

async def main():
    async with AsyncSessionLocal() as db:
        for q in QUERIES:
            print(f"\n{'#'*72}\n查询: {q}")
            plan = await plan_query(q, db=db, owner_id=OWNER)
            print(f"  source={plan.get('source')}")
            core = plan.get('core_entities') or []
            if core:
                print(f"  core_entities(按IDF权重降序):")
                for c in core:
                    print(f"    {c['name']:<16} 权重={c['weight']:<7} df={c['df']:<5} 分类={c['category']}")
            else:
                print("  core_entities=[] (无词典命中)")
            print(f"  terms={plan.get('terms')[:8]}")

if __name__ == "__main__":
    asyncio.run(main())
