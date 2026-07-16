# -*- coding: utf-8 -*-
"""验证:证据驱动裁定(工具组取证→喂模型判)能否冲到接近100%。
复用正式工具组 实体裁定取证工具组.py,零行业硬编码。串行+间隔避 opencode 429。owner=4。
黄金集同 测_GPT语义裁定.py。目标:该留侧乱并=0(精度红线),整体尽量满分。
"""
import asyncio, sys, json
sys.path.insert(0, "backend"); sys.path.insert(0, ".")
from app.database import AsyncSessionLocal
from modules.knowledge.backend.services.实体裁定取证工具组 import 查词频, 查上下文, 差异字定位

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

SYS = (
    "你是中文实体校对专家。判断【原词】是不是【候选词】的错别字误写(该并),还是本身就是独立正常词(该留)。\n"
    "系统已经帮你查好了证据(不用你猜):\n"
    "- 候选词在本知识库干净原文里出现的篇数(篇数高=它是库里权威真实写法)\n"
    "- 原词的篇数(篇数0=库里根本没这个词,大概率是变体误写)\n"
    "- 两词的差异字(第几个字不同,原字→候选字)\n"
    "- 候选词的真实上下文片段(它到底怎么用)\n\n"
    "判【并】:候选词高频、原词篇数≈0、且差异字是形近或音近的误认(如 族↔镞、菁↔精、巢↔薇、缊↔蕴) → 原词是候选词的错写。\n"
    "判【留】:满足任一即留——\n"
    "  · 原词本身在库里也有篇数(它是真实存在的独立词)\n"
    "  · 差异字是常用功能词(的/性/无/不/或/和/为/型/者)\n"
    "  · 差异字导致词义不同甚至相反(利润vs毛利、师vs院、展示vs显示、录播vs直播)\n"
    "拿不准一律判【留】(宁漏勿错)。只输出JSON: {\"判定\":\"并\"或\"留\",\"因\":\"简短\"}"
)


async def 备证据(db, 原词, 候选词):
    候频 = await 查词频(db, OWNER, 候选词)
    原频 = await 查词频(db, OWNER, 原词)
    差 = 差异字定位(原词, 候选词)
    候上下文 = await 查上下文(db, OWNER, 候选词, 条数=3)
    return {
        "原词": 原词, "候选词": 候选词,
        "候选词篇数": 候频, "原词篇数": 原频,
        "差异字": [f"第{d['位']}字 {d['原字']}→{d['候选字']}" for d in 差],
        "候选词上下文": 候上下文,
    }


async def main():
    from app.gateway.router import gateway_router
    ok = merge_wrong = 0
    async with AsyncSessionLocal() as db:
        for 原词, 候选词, expect in GOLD:
            ev = await 备证据(db, 原词, 候选词)
            usr = "证据:\n" + json.dumps(ev, ensure_ascii=False) + "\n\n原词是候选词的错写吗?"
            verdict, reason = "?", ""
            for attempt in range(4):
                try:
                    res = await gateway_router.chat(
                        [{"role": "system", "content": SYS}, {"role": "user", "content": usr}],
                        profile_key="deepseek-v4-flash",
                    )
                    import re
                    m = re.search(r'\{.*\}', res.get("content", ""), re.S)
                    if m:
                        d = json.loads(m.group(0))
                        verdict, reason = d.get("判定", "?"), d.get("因", "")
                        break
                except Exception as e:
                    reason = str(e)[:40]
                await asyncio.sleep(1.5 * (attempt + 1))
            hit = "✓" if verdict == expect else "✗"
            if verdict == expect:
                ok += 1
            elif expect == "留" and verdict == "并":
                merge_wrong += 1
            print(f"  {hit} [{原词}→{候选词}] 候{ev['候选词篇数']}原{ev['原词篇数']} 期望{expect} 判{verdict} ({reason})", flush=True)
            await asyncio.sleep(1.2)
    print(f"\n准确率: {ok}/{len(GOLD)} = {ok/len(GOLD)*100:.0f}%", flush=True)
    print(f"乱并(该留却判并,精度红线): {merge_wrong} 个", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
