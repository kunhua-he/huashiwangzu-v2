# -*- coding: utf-8 -*-
"""直连Ollama测真实本地模型智商(绕过网关fallback)。对比knowledge任务表现。"""
import json, time, urllib.request

OLLAMA = "http://127.0.0.1:11434/api/chat"
MODELS = ["gemma-4-26b:latest", "qwen2.5-14b:latest"]

TASKS = {
    "实体抽取": "从下面护肤品文案抽取实体,输出JSON数组,每个含name和category(产品名/成分/功效/品牌/组织名/术语)。文案:俏小喵舒缓修护面膜含2%积雪草苷和神经酰胺,由华世王镞实验室研发,主打问题肌修护,适合敏感肌。只输出JSON。",
    "描述总结": "把以下关于积雪草苷的碎片综合成一段连贯中文总结,第三人称开头写实体全名整合全部信息:1.从积雪草提取的活性成分 2.促进胶原蛋白合成 3.常用于敏感肌修护 4.浓度0.1%-2%。只输出总结正文。",
    "冲突判断": "判断两条描述是否矛盾输出JSON{\"是否冲突\":bool,\"冲突点\":\"\",\"建议\":\"调和/保留两说/同名不同实体\"}。A:面膜含2%积雪草苷适合敏感肌。B:面膜含5%积雪草苷适合油痘肌。只输出JSON。",
    "查询拆词": "把问题拆成两层关键词输出JSON{\"低层词\":[具体实体成分],\"高层词\":[抽象概念意图]}。问题:俏小喵那款修护面膜里的积雪草苷对敏感肌有没有用浓度多少合适?只输出JSON。",
}

def call(model, prompt):
    body = json.dumps({"model":model,"messages":[{"role":"user","content":prompt}],"stream":False,"options":{"temperature":0.3}}).encode()
    req = urllib.request.Request(OLLAMA, data=body, headers={"Content-Type":"application/json"})
    t0=time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            d=json.load(r)
        dt=round((time.perf_counter()-t0)*1000)
        return dt, d.get("message",{}).get("content","")[:1000]
    except Exception as e:
        return round((time.perf_counter()-t0)*1000), f"ERROR:{e}"[:300]

results=[]
for task,prompt in TASKS.items():
    for m in MODELS:
        dt,out=call(m,prompt)
        results.append({"model":m,"task":task,"ms":dt,"out":out})
        print(f"\n{'='*70}\n【{task}】{m}  {dt}ms\n{'-'*70}\n{out}")
print(f"\n\n耗时汇总(ms):")
print(f"{'任务':<12}", *[f"{m:<22}" for m in MODELS])
for task in TASKS:
    print(f"{task:<12}", *[f"{next(x['ms'] for x in results if x['task']==task and x['model']==m):<22}" for m in MODELS])
json.dump(results,open("开发文档/临时文档/本地模型直连结果.json","w"),ensure_ascii=False,indent=2)
