# -*- coding: utf-8 -*-
"""验证正式裁定循环(实体裁定循环.py)完整跑通:带置信度+留言+留言表落库。
黄金集17例。看:该留侧乱并=0(精度红线);证据不足的(两边0篇)是否进留言表而非瞎判。owner=4。
串行+间隔避 opencode 429。
"""
import asyncio, sys
sys.path.insert(0, "backend"); sys.path.insert(0, ".")
from app.database import AsyncSessionLocal
from modules.knowledge.backend.services.实体裁定循环 import 裁定

OWNER = 4
GOLD = [
    ("华世王族公司", "华世王镞公司", "并"),
    ("华世王链公司", "华世王镞公司", "并"),
    ("青春缊能霜", "青春蕴能霜", "并"),
    ("熙妍菁华液", "熙妍精华液", "并"),
    ("娇巢诗", "娇薇诗", "并"),
    ("苏寇雅", "苏蜜雅", "并"),
    ("筱墨缮采霜", "筱墨蕴采霜", "并"),
    ("皮肤无弹性", "皮肤的弹性", "留"),
    ("项目纯利润", "项目毛利润", "留"),
    ("电子展示屏", "电子显示屏", "留"),
    ("美容师收入", "美容院收入", "留"),
    ("长期不调理", "长期的调理", "留"),
    ("线上录播课", "线上直播课", "留"),
    ("现金或红包", "现金的红包", "留"),
    ("敏感型皮肤", "敏感性皮肤", "留"),
    ("消费者定位", "消费圈定位", "留"),
    ("停车券服务", "停车场服务", "留"),
]


async def main():
    对 = 乱并 = 0
    async with AsyncSessionLocal() as db:
        for 原词, 候选词, expect in GOLD:
            该并 = await 裁定(db, OWNER, 原词, 候选词)
            实际 = "并" if 该并 else "留"
            hit = "✓" if 实际 == expect else "✗"
            if 实际 == expect:
                对 += 1
            elif expect == "留" and 实际 == "并":
                乱并 += 1
            print(f"  {hit} [{原词}→{候选词}] 期望{expect} 裁定{实际}", flush=True)
            await asyncio.sleep(1.2)
    print(f"\n准确率: {对}/{len(GOLD)} = {对/len(GOLD)*100:.0f}%", flush=True)
    print(f"乱并(精度红线): {乱并} 个", flush=True)
    # 查留言表
    async with AsyncSessionLocal() as db:
        from sqlalchemy import text as T
        r = await db.execute(T("SELECT orig_name,cand_name,verdict,confidence,agent_note FROM kb_entity_verdict_review WHERE owner_id=:o ORDER BY id DESC LIMIT 10"), {"o": OWNER})
        rows = r.all()
        print(f"\n留言表待复核 {len(rows)} 条:", flush=True)
        for o, c, v, cf, note in rows:
            print(f"  [{o}→{c}] {v} 置信{cf} — {note}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
