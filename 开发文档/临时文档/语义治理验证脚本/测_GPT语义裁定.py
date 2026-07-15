# -*- coding: utf-8 -*-
"""独立测试:GPT(responses协议)能否干净区分长上下文实体打齐的"该并"vs"该留"。
纯测试,不写库,不碰任何在跑的脚本。用之前真实误伤案例当黄金标准。owner=4。

黄金集来自 2026-07-15 夜实测:
  该并(对的):OCR把生僻错字纠回专名 → GPT应判"并"
  该留(错的):功能词/反义/词义差异的两个真词 → GPT应判"留"
目标:看GPT在这批上的准确率。准了再谈落地。
"""
import asyncio, sys, json, urllib.request
sys.path.insert(0, "backend"); sys.path.insert(0, ".")

GPT_EP = "http://localhost:50936/v1/responses"
GPT_MODEL = "gpt-5.5"
GPT_KEY = "agt_codex_ObOla6ZsThNlW1KdD7Ykmj5ZmH6FFkO1"

# (原词, 候选规范名, 期望判定)  期望: 并=该合并(原是错字) / 留=不该合并(原是真词)
GOLD = [
    # 该并:生僻错字→专名
    ("华世王族公司", "华世王镞公司", "并"),
    ("华世王链公司", "华世王镞公司", "并"),
    ("青春缊能霜", "青春蕴能霜", "并"),
    ("熙妍菁华液", "熙妍精华液", "并"),
    ("娇巢诗", "娇薇诗", "并"),
    ("苏寇雅", "苏蜜雅", "并"),
    ("筱墨缮采霜", "筱墨蕴采霜", "并"),
    # 该留:功能词/反义/词义差异(两个都真词)
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


def _gpt(sys_p, user):
    payload = json.dumps({"model": GPT_MODEL, "input": f"{sys_p}\n\n{user}", "stream": False}).encode()
    req = urllib.request.Request(GPT_EP, data=payload,
                                 headers={"Content-Type": "application/json", "Authorization": f"Bearer {GPT_KEY}"})
    raw = urllib.request.urlopen(req, timeout=60).read()
    d = json.loads(raw)
    text = ""
    for it in d.get("output", []):
        if it.get("type") == "message":
            text += "".join(c.get("text", "") for c in it.get("content", []) if c.get("type") == "output_text")
    return text


SYS = (
    "你是中文实体校对专家,判断【原词】是不是【候选词】的OCR错别字误写。\n"
    "背景:知识库里有OCR识别错误——把生僻字/形近字认错(如'镞'认成'族/链')。需要把这类错写并回正确的。\n"
    "但也有很多'原词本身就是正确的、只是和候选词是不同的词'的情况,这种绝不能并。\n\n"
    "判【并】:原词是候选词的错写——原词那个字是生僻/形近误认,原词整体不是一个有独立含义的正常词。\n"
    "判【留】:原词本身是正常词、有独立且不同的含义(哪怕候选词更常见)。尤其:\n"
    "  - 差异字是常用功能词(的/性/无/不/或/和/为/型/者)→几乎都是留\n"
    "  - 差异导致词义不同甚至相反(纯利润vs毛利润、无弹性vs的弹性、录播vs直播、师vs院)→留\n"
    "拿不准一律判留。只输出JSON: {\"判定\":\"并\"或\"留\",\"因\":\"简短\"}"
)


async def main():
    ok = 0
    for orig, cand, expect in GOLD:
        user = f"原词:{orig}\n候选词:{cand}\n原词是候选词的OCR错写吗?"
        try:
            loop = asyncio.get_event_loop()
            raw = await loop.run_in_executor(None, lambda: _gpt(SYS, user))
            import re
            m = re.search(r'\{.*\}', raw, re.S)
            verdict = json.loads(m.group(0)).get("判定", "?") if m else "?"
            reason = json.loads(m.group(0)).get("因", "") if m else raw[:40]
        except Exception as e:
            verdict, reason = "ERR", str(e)[:40]
        hit = "✓" if verdict == expect else "✗"
        if verdict == expect:
            ok += 1
        print(f"  {hit} [{orig}→{cand}] 期望{expect} GPT判{verdict}  ({reason})", flush=True)
    print(f"\n准确率: {ok}/{len(GOLD)} = {ok/len(GOLD)*100:.0f}%", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
