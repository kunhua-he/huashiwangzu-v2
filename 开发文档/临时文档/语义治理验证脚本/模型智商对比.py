# -*- coding: utf-8 -*-
"""模型智商对比：gpt-5.5-knowledge(本地路由) vs deepseek-v4-flash vs gemma-4(纯本地)
用知识库真实任务题：实体抽取/描述总结/冲突判断/查询双层拆词。"""
import asyncio, json, sys, time
sys.path.insert(0, "backend")
sys.path.insert(0, ".")

from app.gateway.service import chat

PROFILES = ["gpt-5.5-knowledge", "deepseek-v4-flash", "gemma-4"]

# 4道知识库真实任务题（护肤品行业上下文）
TASKS = {
    "实体抽取": [
        {"role": "system", "content": "你是知识图谱实体抽取专家。只输出JSON,不要解释。"},
        {"role": "user", "content": """从下面护肤品文案抽取实体,输出JSON数组,每个实体含 name(名称)、category(分类:产品名/成分/功效/品牌/组织名/人名/地名/术语)。
文案:俏小喵舒缓修护面膜含有2%积雪草苷和神经酰胺,由华世王镞实验室研发,主打问题肌修护,适合敏感肌。RGB色值#0086A8是品牌主色。
只输出JSON。"""}
    ],
    "描述总结": [
        {"role": "system", "content": "你是知识图谱专家,擅长把碎片描述综合成一段连贯总结。第三人称,开头写实体全名,整合全部信息不许漏,中文输出。"},
        {"role": "user", "content": """把以下关于"积雪草苷"的多条碎片描述综合成一段统一描述:
1. 积雪草苷是从积雪草中提取的活性成分。
2. 积雪草苷具有促进胶原蛋白合成的作用。
3. 该成分常用于敏感肌修护类护肤品。
4. 积雪草苷浓度通常在0.1%-2%之间。
只输出总结正文。"""}
    ],
    "冲突判断": [
        {"role": "system", "content": "你是数据质检专家。判断两条描述是否矛盾,只输出JSON。"},
        {"role": "user", "content": """判断以下两条关于同一产品的描述是否存在冲突,输出JSON:{"是否冲突":true/false,"冲突点":"...","建议":"调和/保留两说/同名不同实体"}
描述A:舒缓修护面膜含2%积雪草苷,适合敏感肌。
描述B:舒缓修护面膜含5%积雪草苷,适合油痘肌。
只输出JSON。"""}
    ],
    "查询双层拆词": [
        {"role": "system", "content": "你是检索查询分析专家。把用户问题拆成两层关键词,只输出JSON。"},
        {"role": "user", "content": """把下面的问题拆成两层关键词,输出JSON:{"低层词":["具体实体/产品/成分"],"高层词":["抽象概念/主题/意图"]}
问题:俏小喵那款修护面膜里的积雪草苷对敏感肌到底有没有用,浓度多少合适?
只输出JSON。"""}
    ],
}

async def run_one(profile, task_name, messages):
    t0 = time.perf_counter()
    try:
        resp = await chat(messages=list(messages), profile_key=profile)
        dt = round((time.perf_counter()-t0)*1000)
        content = ""
        if isinstance(resp, dict):
            content = resp.get("content") or resp.get("text") or ""
            if not content and resp.get("choices"):
                content = resp["choices"][0].get("message",{}).get("content","")
        return {"profile":profile,"task":task_name,"ms":dt,"ok":True,"out":str(content)[:1200]}
    except Exception as e:
        dt = round((time.perf_counter()-t0)*1000)
        return {"profile":profile,"task":task_name,"ms":dt,"ok":False,"out":f"ERROR: {e}"[:400]}

async def main():
    results = []
    for task_name, messages in TASKS.items():
        for profile in PROFILES:
            r = await run_one(profile, task_name, messages)
            results.append(r)
            print(f"\n{'='*70}\n【{task_name}】 {profile}  {r['ms']}ms  {'OK' if r['ok'] else 'FAIL'}\n{'-'*70}\n{r['out']}")
    # 汇总
    print(f"\n\n{'#'*70}\n耗时汇总(ms):")
    print(f"{'任务':<16}", *[f"{p:<22}" for p in PROFILES])
    for task_name in TASKS:
        row = [f"{task_name:<16}"]
        for p in PROFILES:
            hit = next((x for x in results if x['task']==task_name and x['profile']==p), None)
            row.append(f"{(str(hit['ms'])+('' if hit['ok'] else '✗')):<22}" if hit else " "*22)
        print(*row)
    json.dump(results, open("开发文档/临时文档/模型智商对比结果.json","w"), ensure_ascii=False, indent=2)
    print("\n结果已存 开发文档/临时文档/模型智商对比结果.json")

if __name__ == "__main__":
    asyncio.run(main())
