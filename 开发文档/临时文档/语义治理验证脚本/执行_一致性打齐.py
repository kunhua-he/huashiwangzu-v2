# -*- coding: utf-8 -*-
"""一致性打齐执行(安全版):形近变体拉齐到高频锚点。
写 canonical_id(指向锚点) + 别名(kb_entity_aliases,让搜变体命中锚点)。
锚点判据=文本层块数(排图片污染)。LLM复核同一实体。DRY_RUN开关。owner_id=4。可回滚。"""
import asyncio, json, sys, re, urllib.request, argparse
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
def chat(s,u,to=180):
    b=json.dumps({"model":MODEL,"messages":[{"role":"system","content":s},{"role":"user","content":u}],"stream":False,"options":{"temperature":0.1}}).encode()
    r=urllib.request.Request(EP,data=b,headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(r,timeout=to) as x: return json.load(x).get("message",{}).get("content","")

async def find_variant_group(db, pattern, structure_desc):
    """找一组形近变体+文本层锚点判据(排图片base_parse污染)。"""
    r=await db.execute(T(f"""
        SELECT ed.id, ed.name,
          -- 锚点判据:真文本层块(排除图片文档的base_parse污染) + fusion块
          COALESCE((SELECT COUNT(*) FROM kb_chunk_entities ce JOIN kb_chunks c ON c.id=ce.chunk_id
            JOIN kb_documents d ON d.id=c.document_id
            WHERE ce.entity_id=ed.id AND ce.owner_id=4
              AND NOT (c.index_layer='base_parse' AND d.extension IN ('jpg','png','jpeg','gif','bmp','webp','tiff'))
          ),0) AS 干净块数,
          COALESCE((SELECT COUNT(*) FROM kb_chunk_entities ce WHERE ce.entity_id=ed.id AND ce.owner_id=4),0) AS 总块数
        FROM kb_entity_dictionary ed
        WHERE ed.owner_id=4 AND ed.status IN ('candidate','confirmed') AND ed.name ~ :pat
        ORDER BY 干净块数 DESC, 总块数 DESC
    """), {"pat":pattern})
    return [(x[0],x[1],x[2],x[3]) for x in r.all()]

async def align_group(db, members, structure_desc, dry_run=True):
    if len(members)<2:
        print(f"  组太小,跳过"); return
    anchor_id, anchor_name = members[0][0], members[0][1]
    variant_names=[m[1] for m in members]
    # LLM复核:基于"实体唯一性"而非"字形",判断是否同一实体的OCR变体
    freq_lines="\n".join(f"  {m[1]} (出现{m[3]}次)" for m in members)
    sys_p="你是实体规范化专家。判断这些名称是否指向现实中同一个实体。关键:判断依据是'现实中是不是同一个东西',不是'字形像不像'。只输出JSON。"
    usr_p=f"""下面是一组结构完全相同的名称({structure_desc}),只有中间一个字不同,带出现频率:
{freq_lines}

推理要点:
1. 这是{structure_desc}——现实中同一个注册全称是唯一的,不可能存在这么多只差一个字的同名公司
2. 出现频率最高的"{anchor_name}"极可能是正确写法,其余低频的是OCR把那个字识别错了
3. 判断依据是"现实中是否同一个实体",不是"两个字长得像不像"

哪些是同一实体(锚点"{anchor_name}")的OCR错字变体、该合并?哪些确实是不同实体(如'商贸'vs'生物科技'才算真不同)?
严格JSON:{{"应合并到锚点":["变体名"],"真不同实体":["名"],"理由":""}}
只输出JSON。"""
    res=rj(chat(sys_p,usr_p)) or {}
    to_merge=set(res.get("应合并到锚点",[]))
    print(f"\n锚点: {anchor_name} (id={anchor_id}, 干净块{members[0][2]})")
    print(f"LLM判定合并: {res.get('应合并到锚点')}")
    print(f"LLM判定不合并: {res.get('真不同实体')}")
    print(f"理由: {str(res.get('理由',''))[:60]}")
    # 写库:合并的变体 canonical_id=anchor + 别名
    written=0
    for mid, mname, _c, _t in members[1:]:
        if mname not in to_merge: continue
        if dry_run:
            print(f"  [DRY] {mname}(id={mid}) → canonical_id={anchor_id} + 别名")
        else:
            await db.execute(T("UPDATE kb_entity_dictionary SET canonical_id=:a WHERE id=:i AND owner_id=:o"),
                             {"a":anchor_id,"i":mid,"o":OWNER})
            exists=await db.execute(T("SELECT 1 FROM kb_entity_aliases WHERE owner_id=:o AND entity_id=:a AND alias=:al"),
                                    {"o":OWNER,"a":anchor_id,"al":mname})
            if not exists.first():
                await db.execute(T("INSERT INTO kb_entity_aliases(owner_id,entity_id,alias,created_at,updated_at) VALUES(:o,:a,:al,now(),now())"),
                                 {"o":OWNER,"a":anchor_id,"al":mname})
        written+=1
    if not dry_run:
        await db.execute(T("UPDATE kb_entity_dictionary SET canonical_id=id WHERE id=:a AND owner_id=:o"),{"a":anchor_id,"o":OWNER})
        await db.commit()
    print(f"  {'预览' if dry_run else '已写'} {written} 个变体拉齐到锚点")

async def main(dry_run=True):
    async with AsyncSessionLocal() as db:
        members = await find_variant_group(db, '^云南华世王.生物科技有限公司$', "云南华世王X生物科技有限公司")
        print(f"华世王X公司名组: {len(members)}个变体")
        await align_group(db, members, "云南华世王X生物科技有限公司", dry_run=dry_run)

if __name__=="__main__":
    ap=argparse.ArgumentParser(); ap.add_argument("--go",action="store_true"); a=ap.parse_args()
    asyncio.run(main(dry_run=not a.go))
