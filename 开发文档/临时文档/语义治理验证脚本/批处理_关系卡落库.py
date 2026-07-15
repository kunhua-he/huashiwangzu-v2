# -*- coding: utf-8 -*-
"""语义治理批处理(小批验证):混沌主体→gemma生成关系卡→落库semantic_meta。
落库后可被召回一次带出。纯原文推导零硬编码。owner_id=4。可回滚(只写semantic_meta新字段)。"""
import asyncio, json, sys, re, urllib.request, time
sys.path.insert(0, "backend"); sys.path.insert(0, ".")
from app.database import AsyncSessionLocal
from sqlalchemy import text as T

OWNER=4; MODEL="gemma-4-26b:latest"; EP="http://127.0.0.1:11434/api/chat"

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

SYS="你是知识库关系卡生成器。给定主体和它出现的原文,复核并生成关系卡。关系必须来自原文,不编造。先判断这个主体在原文里是否真实出现(复核)。只输出JSON。"
TMPL="""主体:{subject}
原文片段:
{context}

严格JSON输出:
{{
 "复核_原文是否真提到该主体": true/false,
 "类型":"人物/成分/品牌/产品/事件/地点/组织/功效/术语等",
 "一句话":"一句自然中文说清它是什么、和谁什么关系(agent一眼懂)",
 "三元组":[{{"主":"","谓":"关系动词","宾":"","据":"原文依据"}}],
 "置信":0.0到1.0
}}
关系只能来自原文。若原文根本没提该主体,复核填false、三元组空。只输出JSON。"""

async def fetch_context(subj):
    """快操作:取主体的id+关联原文。用完立即释放连接。取chunk最多的那个实体(避免同名取错)。"""
    async with AsyncSessionLocal() as db:
        r=await db.execute(T("""
            SELECT ed.id, LEFT(string_agg(DISTINCT c.text, E'\n---\n'), 1600) AS ctx, count(*) AS n
            FROM kb_entity_dictionary ed
            JOIN kb_chunk_entities ce ON ce.entity_id=ed.id AND ce.owner_id=ed.owner_id
            JOIN kb_chunks c ON c.id=ce.chunk_id
            WHERE ed.owner_id=:o AND ed.name=:n GROUP BY ed.id ORDER BY n DESC LIMIT 1
        """), {"o":OWNER,"n":subj})
        row=r.first()
        return (row[0], row[1]) if row else (None, None)

async def save_meta(eid, meta):
    """快操作:写semantic_meta。独立短连接。"""
    async with AsyncSessionLocal() as db:
        await db.execute(T("UPDATE kb_entity_dictionary SET semantic_meta=cast(:m as json) WHERE id=:i AND owner_id=:o"),
                         {"m":json.dumps(meta,ensure_ascii=False),"i":eid,"o":OWNER})
        await db.commit()

async def main():
    subjects=["梁自清","2018美容院周年庆活动方案","微波拉皮仪","店铺负责人","连锁分店","复原"]
    for subj in subjects:
        eid, ctx = await fetch_context(subj)   # 快:取原文,释放连接
        if not eid: print(f"\n【{subj}】无实体"); continue
        t0=time.perf_counter()
        out=chat(SYS, TMPL.format(subject=subj, context=ctx or ""))  # 慢:LLM,不占DB连接
        card=rj(out)
        dt=round((time.perf_counter()-t0)*1000)
        if not isinstance(card,dict): print(f"\n【{subj}】关系卡生成失败:{out[:150]}"); continue
        meta={"关系卡":card,"生成模型":MODEL,"生成时刻":time.strftime("%Y-%m-%d %H:%M")}
        await save_meta(eid, meta)   # 快:写库,独立短连接
        fu=card.get("复核_原文是否真提到该主体")
        print(f"\n【{subj}】{dt}ms 复核={fu} 置信={card.get('置信')}")
        print(f"  一句话: {card.get('一句话')}")
        for tri in card.get("三元组",[])[:4]:
            if isinstance(tri,dict): print(f"    {tri.get('主')} --{tri.get('谓')}--> {tri.get('宾')}")
    print("\n已落库 semantic_meta。")

if __name__=="__main__": asyncio.run(main())
