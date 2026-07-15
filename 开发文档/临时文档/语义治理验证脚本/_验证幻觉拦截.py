# -*- coding: utf-8 -*-
"""专项验证治坑1:同义词合并 + 幻觉拦截。构造含同义词+幻觉诱导词的样本。"""
import json, re, urllib.request
MODEL="gemma-4-26b:latest"; EP="http://127.0.0.1:11434/api/chat"
def norm(s): return re.sub(r"\s+","",str(s or "").strip().lower())
def rj(t):
    if not t: return None
    t=re.sub(r"^```(?:json)?\s*","",t.strip()); t=re.sub(r"\s*```$","",t)
    i,j=t.find("["),t.rfind("]")
    if i!=-1 and j>i:
        try: return json.loads(t[i:j+1])
        except: pass
    return None
def chat(s,u,to=180):
    b=json.dumps({"model":MODEL,"messages":[{"role":"system","content":s},{"role":"user","content":u}],"stream":False,"options":{"temperature":0.1}}).encode()
    r=urllib.request.Request(EP,data=b,headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(r,timeout=to) as x: return json.load(x).get("message",{}).get("content","")

# 含同义词组+幻觉诱导(华世王镞易被误改成王族)
WORDS=["积雪草苷","积雪草甙","积雪草甘","羟基积雪草苷","烟酰胺","烟酰","华世王镞","维生素B3","面膜"]
pool={norm(w) for w in WORDS}
SYS="你是实体合并专家。判断哪些词是同一实体的不同写法,给统一规范名。规范名必须是输入词的原样,禁止改字造词。只输出JSON数组。"
USER=f"""判断下面词的同义关系,输出JSON数组:
[{{"词":"原词","同义规范名":"统一名(必须是输入里出现的原词,不许改任何字)"}}]
词:{"、".join(WORDS)}
只输出JSON。"""
def safe(word, canon):
    if not canon: return word, False, False
    if norm(canon) in pool: return canon, (norm(canon)!=norm(word)), False
    return word, False, True  # 造词,拦截

c=chat(SYS,USER); arr=rj(c)
print("LLM原始返回:")
if isinstance(arr,list):
    blocked=[]; merged=[]
    for it in arr:
        if not isinstance(it,dict): continue
        w=str(it.get("词","")); lc=it.get("同义规范名","")
        final,m,blk=safe(w,lc)
        mark = " ✗幻觉拦截" if blk else (" →合并" if m else "")
        print(f"  {w:<14} LLM给规范名={str(lc):<14} 最终={final}{mark}")
        if blk: blocked.append(f"{w}: LLM想改成'{lc}'被拦")
        if m: merged.append(f"{w}→{final}")
    print(f"\n合并{len(merged)}: {'; '.join(merged)}")
    print(f"幻觉拦截{len(blocked)}: {'; '.join(blocked)}")
else:
    print("解析失败:",c[:300])
