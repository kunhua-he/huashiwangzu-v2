# -*- coding: utf-8 -*-
"""趁GPT额度在,批量实体归类(18类型)。高频实体优先(影响召回的)。
GPT responses协议+X-Session-Id真并行。owner=4。用法: python 批_实体归类.py [--conc 200] [--limit N]
"""
import asyncio, sys, json, time, argparse, urllib.request, uuid
sys.path.insert(0, "backend"); sys.path.insert(0, ".")
from app.database import AsyncSessionLocal
from sqlalchemy import text as T

OWNER = 4
GPT_EP = "http://localhost:50936/v1/responses"
GPT_KEY = "agt_codex_ObOla6ZsThNlW1KdD7Ykmj5ZmH6FFkO1"
TYPES = "成分/原料/功效/品类/产品/品牌/系列/规格/肤质/人物/组织/地点/事件/时间/技术标准/视觉素材/营销内容/噪音"
SYS = (
    f"你是护肤品/化妆品行业实体分类专家。给你一个实体名和当前类目,判断它最准确的类型。\n"
    f"可选类型(严格选一个):{TYPES}\n"
    f"判断规则:\n- 公司/集团/门店=组织\n- 品牌名(如娇薇诗/苏蜜雅/KRNOBQUE)=品牌\n"
    f"- 具体产品(如清颜玻尿酸原液/润颜理肤霜)=产品\n- 产品线(如青春蕴能系列)=系列\n"
    f"- 化学成分(如积雪草苷/玻尿酸/烟酰胺)=成分\n- 原材料=原料\n- 功效描述(美白/祛斑/抗衰)=功效\n"
    f"- 人名=人物\n- 像素/图片格式/OCR标记/技术术语=噪音\n- 拿不准=保持原类目\n"
    f"只输出JSON:{{\"类型\":\"选一个\"}}"
)


async def classify_batch(entities, conc):
    sem = asyncio.Semaphore(conc)
    results = {}

    async def one(eid, name, cat):
        async with sem:
            user = f"实体名:{name}\n当前类目:{cat}\n最准确的类型是?"
            try:
                from app.gateway.router import gateway_router
                res = await gateway_router.chat(
                    [{"role": "system", "content": SYS}, {"role": "user", "content": user}],
                    profile_key="deepseek-v4-flash",
                )
                text = res.get("content", "")
                import re
                m = re.search(r'\{.*\}', text, re.S)
                if m:
                    typ = json.loads(m.group(0)).get("类型", "")
                    if typ in TYPES.split("/"):
                        results[eid] = typ
            except Exception:
                pass
    await asyncio.gather(*(one(e, n, c) for e, n, c in entities))
    return results


async def main(conc, limit):
    async with AsyncSessionLocal() as db:
        r = await db.execute(T(f"""
            SELECT ed.id, ed.name, ed.category,
              (SELECT count(*) FROM kb_chunk_entities ce WHERE ce.entity_id=ed.id AND ce.owner_id={OWNER}) AS blk
            FROM kb_entity_dictionary ed
            WHERE ed.owner_id={OWNER} AND ed.status IN ('candidate','confirmed')
              AND ed.category IN ('术语','通用','其他','产品名','事件')
              AND length(ed.name)>=2
            ORDER BY blk DESC LIMIT :lim
        """), {"lim": limit})
        entities = [(int(i), n, c) for i, n, c, _ in r.all()]
    print(f"待归类: {len(entities)}, 并发={conc}", flush=True)
    t0 = time.time()
    results = await classify_batch(entities, conc)
    print(f"GPT归类完成: {len(results)}/{len(entities)} 用时{time.time()-t0:.0f}s", flush=True)
    # 写回 category(不动type_id,直接改category字段让召回权重生效)
    async with AsyncSessionLocal() as db:
        for eid, typ in results.items():
            await db.execute(T("UPDATE kb_entity_dictionary SET category=:c, updated_at=now() WHERE id=:id AND owner_id=:o"),
                             {"c": typ, "id": eid, "o": OWNER})
        await db.commit()
    print(f"已写回 {len(results)} 个实体类型", flush=True)
    # 统计
    from collections import Counter
    print("类型分布:", Counter(results.values()).most_common(10), flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--conc", type=int, default=200)
    ap.add_argument("--limit", type=int, default=3000)
    a = ap.parse_args()
    asyncio.run(main(a.conc, a.limit))
