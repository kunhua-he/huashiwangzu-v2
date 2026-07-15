# -*- coding: utf-8 -*-
"""通用一致性打齐引擎(文本层字级权威为锚)。全自动、不硬编码。
判据:同结构差一字→归组;查变化字在干净文本层的权威分布;文本层碾压者=正确锚,其他并过去;
无文本层证据时退回总频率悬殊/LLM;LLM兜底。DRY_RUN默认。owner_id=4。"""
import asyncio, json, sys, re, urllib.request, argparse
sys.path.insert(0, "backend"); sys.path.insert(0, ".")
from app.database import AsyncSessionLocal
from sqlalchemy import text as T

OWNER=4; MODEL="gemma-4-26b:latest"; EP="http://127.0.0.1:11434/api/chat"
IMG_EXT="('jpg','png','jpeg','gif','bmp','webp','tiff','svg')"
TEXT_AUTHORITY_RATIO=10   # 文本层最高/次高 >此倍数 = 权威碾压
FREQ_DOMINANT_RATIO=10    # 无文本层时,总频率悬殊阈值

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

async def find_groups(db, category, suffix_pattern):
    """归组:同结构、只差一个字(用＊通配变化字)。返回 {模板: [(id,name,总块)]}。"""
    r=await db.execute(T(f"""
        SELECT ed.id, ed.name,
          regexp_replace(ed.name, '(.)({suffix_pattern})$', '＊\\2') AS tmpl,
          (SELECT COUNT(*) FROM kb_chunk_entities ce WHERE ce.entity_id=ed.id AND ce.owner_id=4) AS blk
        FROM kb_entity_dictionary ed
        WHERE ed.owner_id=4 AND ed.status IN ('candidate','confirmed') AND ed.category=:cat
          AND ed.name ~ ('({suffix_pattern})$') AND length(ed.name)>=6
    """), {"cat":category})
    groups={}
    for eid,name,tmpl,blk in r.all():
        if '＊' not in (tmpl or ''): continue
        groups.setdefault(tmpl, []).append((eid,name,blk or 0))
    return {k:v for k,v in groups.items() if len(v)>=2}

async def text_authority(db, prefix, suffix):
    """查'prefix + X + suffix' 里变化字X在干净文本层的分布(排图片)。返回 {字:块数}。"""
    r=await db.execute(T(f"""
        SELECT substring(c.text from :pat) AS ch, COUNT(*) AS n
        FROM kb_chunks c JOIN kb_documents d ON d.id=c.document_id
        WHERE c.owner_id=4 AND c.index_layer='base_parse'
          AND d.extension NOT IN {IMG_EXT}
          AND c.text ~ (:re)
        GROUP BY substring(c.text from :pat)
    """), {"pat":f"{re.escape(prefix)}(.){re.escape(suffix)}", "re":f"{re.escape(prefix)}.{re.escape(suffix)}"})
    return {ch:n for ch,n in r.all() if ch and ch.strip()}

def split_tmpl(tmpl):
    """＊模板拆成 (prefix, suffix)。"""
    i=tmpl.index('＊'); return tmpl[:i], tmpl[i+1:]

async def _authority_char(db, prefix, suffix):
    """查 prefix+X+suffix 文本层权威字。返回(字,块数,次高)或None。"""
    ta=await text_authority(db, prefix, suffix)
    if not ta: return None
    ranked=sorted(ta.items(), key=lambda x:-x[1])
    top_ch,top_n=ranked[0]; second=ranked[1][1] if len(ranked)>1 else 0
    if top_n>=max(3, second*TEXT_AUTHORITY_RATIO):
        return top_ch, top_n, second
    return None

async def decide_anchor(db, tmpl, members):
    """定锚点判据层级(LLM兜底):
    1.文本层字级权威(本组全称) 2.跨文档缩短前缀查全局权威 3.总频率悬殊 4.需LLM"""
    members=sorted(members, key=lambda m:-m[2])
    prefix,suffix=split_tmpl(tmpl)
    # 层1:全称上下文文本层权威
    hit=await _authority_char(db, prefix, suffix)
    if hit:
        for idx,(eid,name,blk) in enumerate(members):
            if prefix+hit[0]+suffix==name:
                return idx, "文本层权威", f"'{hit[0]}'{hit[1]}块碾压(次{hit[2]})", (prefix,suffix,hit[0],hit[1],hit[2])
    # 层2:跨文档缩短前缀查全局权威字
    for plen in range(len(prefix), 1, -1):
        sub_prefix=prefix[:plen]
        hit=await _authority_char(db, sub_prefix, "")
        if hit:
            correct_name=prefix+hit[0]+suffix  # 用权威字构造正确名
            for idx,(eid,name,blk) in enumerate(members):
                if correct_name==name:  # 组内已有正确形式→用它当锚
                    return idx, "跨文档权威", f"缩前缀'{sub_prefix}'→'{hit[0]}'{hit[1]}块", (sub_prefix,"",hit[0],hit[1],hit[2])
            # 组内全是错字、无正确形式→构造正确锚点(纯规则全自动,不降级)
            return -1, "跨文档构造锚点", f"缩前缀'{sub_prefix}'→权威字'{hit[0]}',构造正确名[{correct_name}]", (sub_prefix,"",hit[0],hit[1],hit[2],correct_name)
    # 层3:总频率悬殊
    if len(members)>=2 and members[0][2]>=max(3, members[1][2]*FREQ_DOMINANT_RATIO):
        return 0, "频率悬殊", f"总频率{members[0][2]}碾压次高{members[1][2]}", None
    # 层4:需LLM兜底
    return 0, "需LLM", "文本层/跨文档/频率均无法判定", None

async def _save_authority(db, detail):
    """把用到的权威字沉淀进全局字典表(缓存,下次快)。"""
    if not detail: return
    pre,suf,ch,cnt,run=detail
    ex=await db.execute(T("SELECT id FROM kb_authority_tokens WHERE owner_id=:o AND context_prefix=:p AND context_suffix=:s AND authority_text=:t"),
                        {"o":OWNER,"p":pre,"s":suf,"t":ch})
    if ex.first(): return
    await db.execute(T("""INSERT INTO kb_authority_tokens(owner_id,context_prefix,context_suffix,authority_text,evidence_count,runner_up_count,source,status,created_at,updated_at)
        VALUES(:o,:p,:s,:t,:e,:r,'text_layer','active',now(),now())"""),
        {"o":OWNER,"p":pre,"s":suf,"t":ch,"e":cnt,"r":run})

async def align_category(db, category, suffix_pattern, dry_run=True, max_groups=8):
    groups=await find_groups(db, category, suffix_pattern)
    print(f"\n{'='*60}\n类目[{category}] 找到 {len(groups)} 个变体组")
    shown=0
    for tmpl, members in sorted(groups.items(), key=lambda x:-sum(m[2] for m in x[1])):
        if shown>=max_groups: break
        shown+=1
        members=sorted(members, key=lambda m:-m[2])
        idx, method, detail, authority = await decide_anchor(db, tmpl, members)
        print(f"\n组[{tmpl}] {len(members)}变体 | 判据={method} | {detail}")
        if idx==-1:  # 构造锚点:组内全错字,用权威字生成正确名
            correct_name=authority[5]
            print(f"  构造正确锚点: [{correct_name}] (库里原本没有,全自动生成)")
            print(f"  待并(全是错字): {', '.join(m[1] for m in members[:6])}")
        else:
            anchor=members[idx]
            print(f"  锚点: {anchor[1]} (id={anchor[0]}, 总块{anchor[2]})")
            others=[m for i,m in enumerate(members) if i!=idx]
            print(f"  待并: {', '.join(m[1] for m in others[:6])}{'...' if len(others)>6 else ''}")
        if method=="需LLM":
            print(f"  ⚠标记存疑(降级LLM/重跑,不纯规则并)")
        elif not dry_run:
            await _save_authority(db, authority)
            await db.commit()

async def main(dry_run=True):
    async with AsyncSessionLocal() as db:
        await align_category(db, "组织名", "生物科技有限公司|商贸有限公司|集团|有限公司", dry_run=dry_run)

if __name__=="__main__":
    ap=argparse.ArgumentParser(); ap.add_argument("--go",action="store_true"); a=ap.parse_args()
    asyncio.run(main(dry_run=not a.go))
