# -*- coding: utf-8 -*-
"""复核+反向推导原型:对着原文验证实体、拆粘连、推关系。归类节点的下一节点。
用华世王镞&梁自清签约案例验证:gemma能否认出粘连、拆原子实体、推出关系。"""
import asyncio, json, sys, re, urllib.request
sys.path.insert(0, "backend"); sys.path.insert(0, ".")
from app.database import AsyncSessionLocal
from sqlalchemy import text as T

OWNER=4; MODEL="gemma-4-26b:latest"; EP="http://127.0.0.1:11434/api/chat"
def rj(t):
    if not t: return None
    t=re.sub(r"^```(?:json)?\s*","",t.strip()); t=re.sub(r"\s*```$","",t)
    for o,c in (("{","}"),("[","]")):
        i,j=t.find(o),t.rfind(c)
        if i!=-1 and j>i:
            try: return json.loads(t[i:j+1])
            except: pass
    return None
def chat(s,u,to=240):
    b=json.dumps({"model":MODEL,"messages":[{"role":"system","content":s},{"role":"user","content":u}],"stream":False,"options":{"temperature":0.1}}).encode()
    r=urllib.request.Request(EP,data=b,headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(r,timeout=to) as x: return json.load(x).get("message",{}).get("content","")

# 粘连实体(抽取时粘一起的)
SUSPECT=["华世王镞 & 梁自清","华世王镞与梁自清签约合作","华世王镞与梁自清签约合作成功打款9999","梁自清"]

SYS="你是知识图谱复核专家。对着原文复核实体:识别粘连(多个实体粘一起)、拆成原子实体、推导实体间关系。只输出JSON。"
TMPL="""下面是从同一批原文抽取的"实体"(可能有粘连/碎片)和原文片段。

疑似实体:{suspects}

原文片段:
{context}

请复核并输出严格JSON:
{{
 "原子实体":[{{"名称":"拆分后的单一实体","类型":"品牌/人物/事件/金额/成分/功效等"}}],
 "关系":[{{"主体":"实体A","关系":"动词短语","客体":"实体B","依据":"原文哪句"}}],
 "废弃实体":[{{"原名":"粘连或碎片实体","原因":"为什么不是合格实体"}}]
}}
只输出JSON。"""

async def main():
    async with AsyncSessionLocal() as db:
        r=await db.execute(T("""
            SELECT DISTINCT LEFT(c.text,200) FROM kb_chunk_entities ce JOIN kb_chunks c ON c.id=ce.chunk_id
            WHERE ce.owner_id=4 AND ce.entity_id IN (72709,73969,72710) LIMIT 4
        """))
        ctx="\n".join(f"- {x[0]}" for x in r.all())
    print("原文片段:\n", ctx[:400], "\n")
    out=chat(SYS, TMPL.format(suspects="、".join(SUSPECT), context=ctx))
    res=rj(out)
    if not isinstance(res,dict):
        print("解析失败:",out[:400]); return
    print("【复核+反推结果】")
    print("\n原子实体(拆粘连后):")
    for e in res.get("原子实体",[]):
        if isinstance(e,dict): print(f"  {e.get('名称')} [{e.get('类型')}]")
    print("\n关系(反向推导,写进图谱):")
    for rel in res.get("关系",[]):
        if isinstance(rel,dict): print(f"  {rel.get('主体')} --{rel.get('关系')}--> {rel.get('客体')}  (依据:{str(rel.get('依据',''))[:30]})")
    print("\n废弃实体(粘连/碎片,标记不合格):")
    for d in res.get("废弃实体",[]):
        if isinstance(d,dict): print(f"  ✗ {d.get('原名')} — {d.get('原因')}")

if __name__=="__main__": asyncio.run(main())
