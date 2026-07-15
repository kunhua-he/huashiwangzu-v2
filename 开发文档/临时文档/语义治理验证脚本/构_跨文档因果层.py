# -*- coding: utf-8 -*-
"""第五层:跨文档因果/层级搭建(独立表 kb_doc_subjects + kb_doc_relations)。

第一性原理(华哥场景):华世王镞集团→5品牌→每品牌多产品海报/货盘。搭方向性归属树。
纯本地、数据驱动、不硬编码行业:
  主体 = 文档最高频中心实体(canonical合并后)。
  同级 = 同主体的多份资料。
  归属 = A文档提到B的主体,且B主体全局文档频率 >> A主体(B更宽泛=上层)→ A归属B。
owner=4。用法: python 构_跨文档因果层.py [--rebuild] [--limit N]
  阶段1 build_subjects:每文档定主体,写 kb_doc_subjects
  阶段2 infer_relations:同级+归属,写 kb_doc_relations
"""
import asyncio, sys, json, time, argparse
from collections import defaultdict
sys.path.insert(0, "backend"); sys.path.insert(0, ".")
from app.database import AsyncSessionLocal
from sqlalchemy import text as T

OWNER = 4
BELONG_FREQ_RATIO = 5      # B主体全局文档数 ≥ A主体 × 此倍数 = B更宽泛,A归属B
SUBJECT_MIN_FREQ = 1       # 主体实体在文档最少出现次数
# 类型权重:专名类更可能是主体(数据驱动兜底,非行业硬编码——只分"具体专名 vs 泛化词/噪音")
CAT_WEIGHT = {"人物": 3, "组织": 3, "品牌": 3, "产品": 3, "系列": 3, "地点": 2, "事件": 2,
              "成分": 2, "原料": 2, "功效": 2, "品类": 2, "技术标准": 2,
              "术语": 1, "通用": 1, "其他": 1, "噪音": 0, "视觉素材": 1, "营销内容": 1}

import re as _re
# 通用提取伪影/技术噪声(非行业硬编码,是OCR/VLM/管线残留的普适垃圾),不能当主体
_NOISE_PAT = _re.compile(
    r"(px|RGB|#[0-9a-fA-F]{3,6}|第[123一二三]轮|视觉构成|视觉轮廓|截图\s*OCR|OCR|blank_like|photo_like|"
    r"Published|平均亮度|边缘密度|主色|模式$|检验报告|价目表|操作[前后]|BEFORE|AFTER)", _re.I)
# 泛化文档类型词(出现在太多文档=不是"某个主体",是资料类别),按全局宽泛度动态挡


def _is_noise_subject(name: str, cat: str) -> bool:
    if not name or cat == "噪音":
        return True
    if _NOISE_PAT.search(name):
        return True
    # 纯英文/数字/符号码(如 ilac-MRA、纯hash)——中文品牌才是主体
    if not _re.search(r"[一-鿿]", name):
        return True
    return False


async def build_subjects(db, limit=None):
    """每文档定主体:该文档 chunk_entities 里,freq×类型权重最高的实体。写 kb_doc_subjects。"""
    lim = f"LIMIT {int(limit)}" if limit else ""
    # 文档→实体→(freq,category);合并后的实体用 canonical 归一
    r = await db.execute(T(f"""
        SELECT ce.document_id, COALESCE(ed.canonical_id, ed.id) AS eid,
               count(*) AS freq,
               max(ed.category) AS category,
               max(COALESCE(canon.name, ed.name)) AS name
        FROM kb_chunk_entities ce
        JOIN kb_entity_dictionary ed ON ed.id=ce.entity_id AND ed.owner_id=ce.owner_id
        LEFT JOIN kb_entity_dictionary canon ON canon.id=ed.canonical_id AND canon.owner_id=ce.owner_id
        WHERE ce.owner_id={OWNER}
        GROUP BY ce.document_id, COALESCE(ed.canonical_id, ed.id)
    """))
    import math
    doc_ents = defaultdict(list)  # doc -> [(eid,freq,cat,name)]
    ent_docfreq = defaultdict(int)  # eid -> 全局文档数(算IDF压样板)
    for did, eid, freq, cat, name in r.all():
        doc_ents[int(did)].append((int(eid), int(freq), cat or "通用", name or ""))
        ent_docfreq[int(eid)] += 1
    total_docs = max(len(doc_ents), 1)

    def _score(e):
        # freq × 类型权重 × IDF(全局越常见=样板=越低分)。样板"检验报告/化验室"被压下去。
        eid, freq, cat, name = e
        idf = math.log((total_docs + 1) / (ent_docfreq.get(eid, 1) + 1)) + 1
        return freq * CAT_WEIGHT.get(cat, 1) * idf

    docs = sorted(doc_ents.keys())
    if limit:
        docs = docs[:int(limit)]
    await db.execute(T("DELETE FROM kb_doc_subjects WHERE owner_id=:o"), {"o": OWNER})
    n = 0
    for did in docs:
        ents = doc_ents[did]
        # 先滤噪声(技术伪影/纯英文码/噪音类),再按 freq×类型×IDF 排
        clean = [e for e in ents if not _is_noise_subject(e[3], e[2])]
        if not clean:
            continue
        ranked = sorted(clean, key=lambda e: -_score(e))
        seid, sfreq, scat, sname = ranked[0]
        if sfreq < SUBJECT_MIN_FREQ:
            continue
        secondary = [{"eid": e[0], "name": e[3], "cat": e[2], "freq": e[1]} for e in ranked[1:8]]
        await db.execute(T("""
            INSERT INTO kb_doc_subjects(owner_id,document_id,subject_entity_id,subject_name,subject_category,freq,secondary_json,status,created_at,updated_at)
            VALUES(:o,:d,:e,:n,:c,:f,CAST(:s AS json),'active',now(),now())
        """), {"o": OWNER, "d": did, "e": seid, "n": sname[:256], "c": scat, "f": sfreq,
               "s": json.dumps(secondary, ensure_ascii=False)})
        n += 1
        if n % 500 == 0:
            await db.commit(); print(f"  ...主体 {n}", flush=True)
    await db.commit()
    print(f"阶段1完成: {n} 文档定主体", flush=True)
    return n


async def infer_relations(db):
    """阶段2:同级(同主体) + 归属(A提到B主体且B主体全局更宽泛)。写 kb_doc_relations。"""
    # 读所有文档主体
    r = await db.execute(T("""
        SELECT document_id, subject_entity_id, subject_name, subject_category, secondary_json
        FROM kb_doc_subjects WHERE owner_id=:o AND subject_entity_id IS NOT NULL
    """), {"o": OWNER})
    rows = r.all()
    subj_of = {}       # doc -> (eid, name, cat)
    secondaries = {}   # doc -> set(secondary eid)
    subj_doc_count = defaultdict(int)  # subject eid -> 有多少文档以它为主体
    for did, seid, sname, scat, sec in rows:
        subj_of[int(did)] = (int(seid), sname, scat)
        sec_ids = set()
        if sec:
            sec_list = sec if isinstance(sec, list) else json.loads(sec)
            sec_ids = {int(x["eid"]) for x in sec_list if x.get("eid")}
        secondaries[int(did)] = sec_ids
        subj_doc_count[int(seid)] += 1

    # 全局:每个实体作为主体或次要,出现在多少文档(衡量"宽泛度")
    ent_doc_breadth = defaultdict(set)
    for did, seid, _, _, sec in rows:
        ent_doc_breadth[int(seid)].add(int(did))
        if sec:
            sec_list = sec if isinstance(sec, list) else json.loads(sec)
            for x in sec_list:
                if x.get("eid"):
                    ent_doc_breadth[int(x["eid"])].add(int(did))
    breadth = {e: len(ds) for e, ds in ent_doc_breadth.items()}

    await db.execute(T("DELETE FROM kb_doc_relations WHERE owner_id=:o"), {"o": OWNER})

    # 同级:同主体的文档两两配(只存一方向,量大只连到该组第一篇当代表,避免N²爆炸)
    by_subject = defaultdict(list)
    for did, (seid, _, _) in subj_of.items():
        by_subject[seid].append(did)
    sib = 0
    for seid, docs in by_subject.items():
        if len(docs) < 2:
            continue
        docs = sorted(docs)
        rep = docs[0]
        sname = subj_of[rep][1]
        for d in docs[1:]:
            await db.execute(T("""
                INSERT INTO kb_doc_relations(owner_id,source_document_id,target_document_id,relation_type,
                  source_subject,target_subject,confidence,evidence,meta_json,status,created_at,updated_at)
                VALUES(:o,:s,:t,'同级',:sn,:tn,:cf,:ev,CAST(:m AS json),'active',now(),now())
            """), {"o": OWNER, "s": d, "t": rep, "sn": sname, "tn": sname, "cf": 0.95,
                   "ev": f"同主体[{sname}]", "m": json.dumps({"subject_eid": seid, "group_size": len(docs)}, ensure_ascii=False)})
            sib += 1
    await db.commit()
    print(f"  同级关系: {sib}", flush=True)

    # 归属:A文档的主体,若在B文档以某更宽泛实体为主体、且该实体出现在A的实体集→A归属B(取最宽泛的一个父)
    belong = 0
    for did, (seid, sname, scat) in subj_of.items():
        a_breadth = breadth.get(seid, 1)
        # A 提到的所有实体(主体+次要)
        a_ents = {seid} | secondaries.get(did, set())
        # 候选父:A提到的实体里,是别的文档主体、且宽泛度>>A主体的
        best_parent = None
        for cand_eid in a_ents:
            if cand_eid == seid:
                continue
            if subj_doc_count.get(cand_eid, 0) < 1:
                continue  # 必须是某文档的主体
            cand_breadth = breadth.get(cand_eid, 0)
            if cand_breadth >= max(2, a_breadth * BELONG_FREQ_RATIO):
                if best_parent is None or cand_breadth > best_parent[1]:
                    best_parent = (cand_eid, cand_breadth)
        if not best_parent:
            continue
        # 找一篇以该父实体为主体的代表文档
        parent_docs = by_subject.get(best_parent[0], [])
        if not parent_docs:
            continue
        parent_doc = sorted(parent_docs)[0]
        if parent_doc == did:
            continue
        pname = subj_of[parent_doc][1]
        await db.execute(T("""
            INSERT INTO kb_doc_relations(owner_id,source_document_id,target_document_id,relation_type,
              source_subject,target_subject,confidence,evidence,meta_json,status,created_at,updated_at)
            VALUES(:o,:s,:t,'归属',:sn,:tn,:cf,:ev,CAST(:m AS json),'active',now(),now())
        """), {"o": OWNER, "s": did, "t": parent_doc, "sn": sname, "tn": pname, "cf": 0.7,
               "ev": f"[{sname}](宽泛度{a_breadth})归属[{pname}](宽泛度{best_parent[1]})",
               "m": json.dumps({"child_subj": seid, "parent_subj": best_parent[0]}, ensure_ascii=False)})
        belong += 1
        if belong % 500 == 0:
            await db.commit(); print(f"  ...归属 {belong}", flush=True)
    await db.commit()
    print(f"  归属关系: {belong}", flush=True)
    return sib, belong


async def main(rebuild, limit):
    async with AsyncSessionLocal() as db:
        t0 = time.time()
        n = await build_subjects(db, limit)
        sib, belong = await infer_relations(db)
        print(f"\n完成: 主体{n} 同级{sib} 归属{belong} 用时{time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--rebuild", action="store_true")
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args()
    asyncio.run(main(a.rebuild, a.limit))
