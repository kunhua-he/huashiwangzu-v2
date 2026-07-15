# -*- coding: utf-8 -*-
"""关系卡预生成验证:随机混沌主体→拿关联原文→gemma推关系卡(三元组+小结)。
验证一次召回能否命中完整因果关系。纯原文推导,零硬编码行业。owner_id=4。"""
import asyncio, json, sys, re, urllib.request
sys.path.insert(0, "backend"); sys.path.insert(0, ".")
from app.database import AsyncSessionLocal
from sqlalchemy import text as T

OWNER=4; MODEL="gemma-4-26b:latest"; EP="http://127.0.0.1:11434/api/chat"
SUBJECTS = ["2018美容院周年庆活动方案","微波拉皮仪","店铺负责人","天津","连锁分店","复原"]

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

SYS="你是知识库关系卡生成器。给定一个主体和它出现的原文,推导这个主体的关系卡:它是什么、和谁有什么关系。关系必须来自原文,不许编造。只输出JSON。"
TMPL="""主体:{subject}

它出现的原文片段:
{context}

生成这个主体的关系卡,严格JSON:
{{
 "主体":"{subject}",
 "类型":"人物/成分/品牌/产品/事件/地点/组织/功效等(从原文判断)",
 "一句话":"用一句自然中文说清这个主体是什么、和谁什么关系(给人一眼看懂)",
 "关系三元组":[{{"主体":"","关系":"动词短语","客体":"","依据":"原文哪句"}}],
 "是否粘连":"若主体名本身是多个实体粘在一起,说明该拆成什么"
}}
关系只能来自原文。只输出JSON。"""

async def main():
    async with AsyncSessionLocal() as db:
        for subj in SUBJECTS:
            r=await db.execute(T("""
                SELECT DISTINCT LEFT(c.text,180) FROM kb_entity_dictionary ed
                JOIN kb_chunk_entities ce ON ce.entity_id=ed.id AND ce.owner_id=ed.owner_id
                JOIN kb_chunks c ON c.id=ce.chunk_id
                WHERE ed.owner_id=:o AND ed.name=:n LIMIT 5
            """), {"o":OWNER,"n":subj})
            ctx="\n".join(f"- {x[0]}" for x in r.all())
            print(f"\n{'='*70}\n主体:【{subj}】")
            if not ctx.strip():
                print("  无原文"); continue
            out=chat(SYS, TMPL.format(subject=subj, context=ctx))
            card=rj(out)
            if not isinstance(card,dict):
                print("  解析失败:",out[:200]); continue
            print(f"  类型: {card.get('类型')}")
            print(f"  ★一句话(给agent): {card.get('一句话')}")
            print(f"  关系三元组(给程序):")
            for tri in card.get("关系三元组",[]):
                if isinstance(tri,dict):
                    print(f"    {tri.get('主体')} --{tri.get('关系')}--> {tri.get('客体')}")
            stick=card.get("是否粘连")
            if stick and str(stick).strip() and str(stick)!="否":
                print(f"  ⚠粘连: {stick}")

if __name__=="__main__": asyncio.run(main())
