# -*- coding: utf-8 -*-
"""测OCR变体合并:公司名"华世王镞"被OCR拆成几十个形近字,能否合并选对规范名。
华哥要点:规范名=用户会搜的最精准公司命名,优先中文,频率+LLM双保险,不被高频错字带偏。"""
import json, re, urllib.request
MODEL="gemma-4-26b:latest"; EP="http://127.0.0.1:11434/api/chat"
def rj(t):
    if not t: return None
    t=re.sub(r"^```(?:json)?\s*","",t.strip()); t=re.sub(r"\s*```$","",t)
    i,j=t.find("{"),t.rfind("}")
    if i!=-1 and j>i:
        try: return json.loads(t[i:j+1])
        except: pass
    return None
def chat(s,u,to=240):
    b=json.dumps({"model":MODEL,"messages":[{"role":"system","content":s},{"role":"user","content":u}],"stream":False,"options":{"temperature":0.1}}).encode()
    r=urllib.request.Request(EP,data=b,headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(r,timeout=to) as x: return json.load(x).get("message",{}).get("content","")

# 真实OCR变体簇(名字, chunk频率)
VARIANTS=[
    ("云南华世王镞生物科技有限公司",95),("云南华世王簇生物科技有限公司",42),("云南华世王族生物科技有限公司",28),
    ("云南华世王镞",32),("云南华世王簇",7),("云南华世王族",7),("云南华世王镁",5),
    ("云南华世王镞商贸有限公司",6),("云南华世王皓生物科技有限公司",2),("云南华世王皙生物科技有限公司",1),
    ("云南华世王锗生物科技有限公司",1),("云南华世王缔",1),("俏小喵",41),
]
lines="\n".join(f"  {n} (出现{c}次)" for n,c in VARIANTS)
pool={re.sub(r"\s+","",n.lower()) for n,_ in VARIANTS}

SYS="你是实体规范化专家。给定一批实体名及出现频率,识别哪些是同一实体的不同写法(含OCR形近错字),给每组选一个规范名。只输出JSON。"
USER=f"""下面实体名可能含OCR形近错字(同一个字被认成不同字)。判断哪些是同一实体,每组选规范名。

规则:
1. 规范名必须是输入里出现过的原词原样,禁止造新词
2. 优先选出现频率高的(高频通常是正确写法)
3. 规范名选"完整、精准、像正式命名"的那个
4. 不同实体不要强行合并

实体名(带频率):
{lines}

严格JSON输出:
{{"合并组":[{{"规范名":"","成员":["",""],"理由":""}}],"独立实体":["没有同义的"]}}
只输出JSON。"""

c=chat(SYS,USER); res=rj(c)
if not isinstance(res,dict):
    print("解析失败:",c[:400])
else:
    print("【OCR变体合并结果】\n")
    for g in res.get("合并组",[]):
        if not isinstance(g,dict): continue
        canon=g.get("规范名",""); ok = re.sub(r"\s+","",str(canon).lower()) in pool
        flag = "" if ok else " ✗规范名造词(拦截,退回最高频)"
        print(f"规范名: {canon}{flag}")
        print(f"  成员: {', '.join(g.get('成员',[]))}")
        print(f"  理由: {str(g.get('理由',''))[:50]}\n")
    if res.get("独立实体"):
        print("独立实体:", res.get("独立实体"))
