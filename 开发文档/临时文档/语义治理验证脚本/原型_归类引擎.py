# -*- coding: utf-8 -*-
"""归类引擎原型:用固化的18类给混沌实体归类+安全合并。三坑治法全落地。
治坑1:规范名安全校验(LLM造新词→拦截退回原名)。治坑2:固定类型不自由发现。治坑3:prompt带反例。"""
import asyncio, json, sys, time, re, urllib.request
sys.path.insert(0, "backend"); sys.path.insert(0, ".")
from app.database import AsyncSessionLocal
from sqlalchemy import text as T

OWNER = 4
MODEL = "gemma-4-26b:latest"
EP = "http://127.0.0.1:11434/api/chat"

def robust_json(text):
    if not text: return None
    t = re.sub(r"^```(?:json)?\s*","",text.strip()); t = re.sub(r"\s*```$","",t)
    for o,c in (("[","]"),("{","}")):
        i,j = t.find(o), t.rfind(c)
        if i!=-1 and j>i:
            try: return json.loads(t[i:j+1])
            except Exception: pass
    return None

def chat(system, user, timeout=240):
    body = json.dumps({"model":MODEL,"messages":[{"role":"system","content":system},{"role":"user","content":user}],"stream":False,"options":{"temperature":0.1}}).encode()
    req = urllib.request.Request(EP, data=body, headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r: d=json.load(r)
    return d.get("message",{}).get("content","")

def norm(s): return re.sub(r"\s+","",str(s or "").strip().lower())

async def load_types():
    async with AsyncSessionLocal() as db:
        r = await db.execute(T("SELECT type_name,definition,examples,counter_examples,is_noise FROM kb_semantic_types WHERE owner_id=:o ORDER BY sort_order"),{"o":OWNER})
        return [{"name":x[0],"def":x[1],"ex":x[2],"cex":x[3],"noise":x[4]} for x in r.all()]

def build_type_prompt(types):
    lines=[]
    for t in types:
        ex="、".join(t["ex"][:4]); cex="、".join(t["cex"][:3]) if t["cex"] else "无"
        tag="【噪音类】" if t["noise"] else ""
        lines.append(f"- {t['name']}{tag}: {t['def']}。例:{ex}。不要归到这类的:{cex}")
    return "\n".join(lines)

CLS_SYS = "你是实体归类专家。只能用给定的固定类型,不要创造新类型。只输出JSON数组,不解释。"
CLS_TMPL = """固定类型体系(只能从这里选):
{types}

给下面每个词判定,严格输出JSON数组,每个元素:
{{"词":"原词原样","类型":"上面类型之一","是实体":true/false,"同义规范名":"若和别的词是同一实体,填统一名;规范名必须是这批词里出现过的原词,不许自己造新写法"}}

严禁:改动词的任何字、创造新词。规范名只能从输入的词里选。

词列表:
{names}
只输出JSON数组。"""

def safe_canonical(word, llm_canon, name_pool_norm):
    """治坑1:规范名安全校验。LLM给的规范名必须∈输入词池,否则判为造词,退回原词。"""
    if not llm_canon: return word, False
    if norm(llm_canon) in name_pool_norm:
        return llm_canon, (norm(llm_canon)!=norm(word))
    return word, False  # LLM造了新词(如王镞→王族),拦截,退回原词

async def main():
    types = await load_types()
    type_prompt = build_type_prompt(types)
    valid_types = {t["name"] for t in types}
    sample = json.load(open("开发文档/临时文档/_混沌样本.json", encoding="utf-8"))
    names = [x["name"] for x in sample]
    name_pool_norm = {norm(n) for n in names}
    print(f"固定类型{len(types)}类 | 混沌样本{len(names)}个 | 模型{MODEL}")

    allcls=[]; blocked=[]
    for i in range(0, len(names), 40):
        batch = names[i:i+40]
        t0=time.perf_counter()
        c = chat(CLS_SYS, CLS_TMPL.format(types=type_prompt, names="、".join(batch)))
        cls = robust_json(c)
        if isinstance(cls, dict): cls = next((v for v in cls.values() if isinstance(v,list)),[])
        dt=round((time.perf_counter()-t0)*1000)
        n_ok = len(cls) if isinstance(cls,list) else 0
        print(f"  [批{i//40+1}] {dt}ms 归类{n_ok}")
        if isinstance(cls,list):
            for it in cls:
                if not isinstance(it,dict): continue
                w=str(it.get("词","")); ty=str(it.get("类型"))
                # 治坑1:安全合并校验
                canon, merged = safe_canonical(w, it.get("同义规范名"), name_pool_norm)
                if it.get("同义规范名") and norm(it.get("同义规范名")) not in name_pool_norm:
                    blocked.append(f"{w}→{it.get('同义规范名')}(拦截)")
                # 治坑2:类型必须∈固定体系
                if ty not in valid_types: ty="噪音"
                allcls.append({"词":w,"类型":ty,"是实体":it.get("是实体"),"规范名":canon,"合并":merged})

    from collections import defaultdict
    bytype=defaultdict(list); noise=[]; merged_pairs=[]
    for it in allcls:
        if not it.get("是实体") or it["类型"]=="噪音": noise.append(it["词"])
        else: bytype[it["类型"]].append(it["词"])
        if it.get("合并"): merged_pairs.append(f"{it['词']}→{it['规范名']}")
    print(f"\n{'='*60}\n归类{len(allcls)} | 有效类型{len(bytype)} | 噪音{len(noise)} | 合并{len(merged_pairs)} | 幻觉拦截{len(blocked)}")
    for ty,ws in sorted(bytype.items(),key=lambda x:-len(x[1])):
        print(f"  【{ty}】{len(ws)}: {', '.join(ws[:10])}")
    print(f"\n  噪音{len(noise)}: {', '.join(noise[:20])}")
    print(f"\n  ★幻觉拦截(治坑1生效){len(blocked)}: {'; '.join(blocked[:12])}")
    print(f"  安全合并{len(merged_pairs)}: {'; '.join(merged_pairs[:12])}")
    json.dump(allcls, open("开发文档/临时文档/_归类结果.json","w"), ensure_ascii=False, indent=1)

if __name__=="__main__": asyncio.run(main())
