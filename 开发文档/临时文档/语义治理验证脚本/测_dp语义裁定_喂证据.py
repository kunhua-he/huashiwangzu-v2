# -*- coding: utf-8 -*-
"""护栏8精度攻坚:把算法手里的铁证全喂给模型,看命中率能否冲到接近100%。
喂三样:① 候选词在本库干净文本层出现N篇(权威度) ② 原词出现M篇(变体佐证)
        ③ 差异字精确定位(原词第i字'X'被认成候选词的'Y',问这俩是否形近/音近误认)
第一性原理:文本层100%正确→候选高频=它对;差异字形近=OCR错认该并,差异字是不同词=该留。
串行+间隔避429。纯测试不写库。owner=4。
"""
import asyncio, sys, json, time
sys.path.insert(0, "backend"); sys.path.insert(0, ".")
from app.database import AsyncSessionLocal
from sqlalchemy import text as T

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
    "你是中文实体校对专家。知识库有OCR错字(把生僻/形近字认错,如'镞'认成'族/链')需并回正确名;\n"
    "但也有'原词本是正确独立词、只是和候选词不同'的,绝不能并。\n"
    "给你的证据(本库文本层100%正确):候选词出现篇数=它是不是权威真名的铁证;原词篇数;以及差异字定位。\n\n"
    "判【并】(原词是候选词的OCR错写),需同时满足:\n"
    "  a) 候选词在本库真实高频出现(是权威真名),原词几乎不出现;\n"
    "  b) 差异字是形近字或音近字的误认(族↔镞、菁↔精、寇↔蜜、巢↔薇、缊↔蕴都是形近)。\n"
    "判【留】(不能并):差异字不是形近误认,而是换了个不同含义的字——\n"
    "  尤其常用功能词(的/性/无/不/或/和/为/型)或导致词义不同(无↔的、师↔院、录↔直、券↔场、者↔圈)。\n"
    "核心:差异字'形近误认'才并;差异字'另一个正常字、换了词义'一律留。拿不准判留。\n"
    "只输出JSON: {\"判定\":\"并\"或\"留\",\"因\":\"简短\"}"
)


async def _attest(db, name):
    r = await db.execute(T("""
        SELECT count(DISTINCT c.document_id) FROM kb_chunks c JOIN kb_documents d ON d.id=c.document_id
        WHERE c.owner_id=:o AND c.index_layer='base_parse'
          AND d.extension NOT IN ('.jpg','.jpeg','.png','.gif','.bmp','.webp','.tiff','.svg')
          AND c.text LIKE :w
    """), {"o": OWNER, "w": f"%{name}%"})
    return int(r.first()[0])


def _diff_chars(orig, cand):
    """等长逐位比差异字。返回[(位置,原字,候选字)]。"""
    if len(orig) != len(cand):
        return []
    return [(i + 1, o, c) for i, (o, c) in enumerate(zip(orig, cand)) if o != c]


async def main():
    from app.gateway.router import gateway_router
    ok = merge_wrong = 0
    async with AsyncSessionLocal() as db:
        for orig, cand, expect in GOLD:
            cand_n = await _attest(db, cand)
            orig_n = await _attest(db, orig)
            diffs = _diff_chars(orig, cand)
            diff_desc = "、".join(f"第{i}字'{o}'被认成'{c}'" for i, o, c in diffs) or "整词不同"
            user = (
                f"原词:{orig}(本库出现{orig_n}篇)\n"
                f"候选词:{cand}(本库出现{cand_n}篇)\n"
                f"差异:{diff_desc}\n"
                f"原词是候选词的OCR错写吗?候选词高频=它是权威真名;差异字若形近误认则并,若是换了含义的另一个字则留。"
            )
            verdict, reason = "?", ""
            for attempt in range(4):
                try:
                    res = await gateway_router.chat(
                        [{"role": "system", "content": SYS}, {"role": "user", "content": user}],
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
            print(f"  {hit} [{orig}({orig_n})→{cand}({cand_n})] 期望{expect} dp判{verdict}  ({reason})", flush=True)
            await asyncio.sleep(1.2)
    print(f"\n准确率: {ok}/{len(GOLD)} = {ok/len(GOLD)*100:.0f}%", flush=True)
    print(f"乱并(该留却判并,精度红线): {merge_wrong} 个", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
