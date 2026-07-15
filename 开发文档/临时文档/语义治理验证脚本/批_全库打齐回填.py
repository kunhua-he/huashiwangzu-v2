# -*- coding: utf-8 -*-
"""全库语义打齐回填(存量清洗)。两遍法+文本层字级权威尺子。全自动、零LLM、可断点续。

第一遍:被chunk引用、含汉字、非merged,且实体名在干净文本层"查无此串"的 = 潜在变体(约2万)。
        实体名文本层能命中的=干净名,直接淘汰(不进第二遍)。
第二遍:对潜在变体逐个跑 canonicalize_name(逐字滑窗+改后完整名文本层命中护栏)。
        变了→并入锚点(chunk_entities改指向/别名/merged/日志)。臆造改写→护栏驳回不动。

进度落盘 /tmp/全库打齐进度.json,已处理id集合,可Ctrl+C后重跑续上。owner_id=4。
用法: python 批_全库打齐回填.py [--limit N] [--reset]
"""
import asyncio, sys, json, time, os, argparse
sys.path.insert(0, "backend"); sys.path.insert(0, ".")
from app.database import AsyncSessionLocal
from sqlalchemy import text as T
from modules.knowledge.backend.services.semantic_align_service import (
    canonicalize_name, _resolve_canonical_entity, _merge_variant_into,
)

OWNER = 4
PROGRESS = "/tmp/全库打齐进度.json"
IMG = "('jpg','png','jpeg','gif','bmp','webp','tiff','svg')"


def load_progress():
    if os.path.exists(PROGRESS):
        try:
            return set(json.load(open(PROGRESS)))
        except Exception:
            return set()
    return set()


def save_progress(done):
    json.dump(sorted(done), open(PROGRESS, "w"))


async def fetch_candidates(db):
    """第一遍:潜在变体(文本层查无此串)。短名优先(真变体多是短专名)。"""
    r = await db.execute(T(f"""
        SELECT e.id, e.name, e.category FROM (
            SELECT DISTINCT ed.id, ed.name, ed.category FROM kb_chunk_entities ce
            JOIN kb_entity_dictionary ed ON ed.id=ce.entity_id AND ed.owner_id=ce.owner_id
            WHERE ce.owner_id={OWNER} AND ed.status!='merged'
              AND length(ed.name)>=2 AND ed.name ~ '[一-鿿]'
        ) e
        WHERE NOT EXISTS (
            SELECT 1 FROM kb_chunks c JOIN kb_documents d ON d.id=c.document_id
            WHERE c.owner_id={OWNER} AND c.index_layer='base_parse'
              AND d.extension NOT IN {IMG}
              AND c.text LIKE '%'||e.name||'%'
        )
        ORDER BY length(e.name), e.id
    """))
    return [(int(i), n, c) for i, n, c in r.all()]


async def main(limit=None, reset=False):
    if reset and os.path.exists(PROGRESS):
        os.remove(PROGRESS)
    done = load_progress()
    async with AsyncSessionLocal() as db:
        cands = await fetch_candidates(db)
    print(f"潜在变体 {len(cands)} 个,已处理 {len(done)},本次待处理 {len(cands)-len(done)}", flush=True)

    processed = aligned = 0
    t0 = time.time()
    for eid, name, category in cands:
        if eid in done:
            continue
        if limit and processed >= limit:
            break
        try:
            async with AsyncSessionLocal() as db:  # 每实体独立短会话,防长事务/连接超时
                canonical_name, fixes = await canonicalize_name(db, OWNER, name)
                if fixes and canonical_name != name:
                    cid = await _resolve_canonical_entity(db, OWNER, canonical_name, category)
                    await _merge_variant_into(db, OWNER, eid, name, cid, canonical_name, fixes)
                    await db.commit()
                    aligned += 1
                    print(f"  [{aligned}] {name} → {canonical_name}  {[(f['from'],f['to']) for f in fixes]}", flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f"  !实体{eid}({name})打齐异常: {exc}", flush=True)
        done.add(eid)
        processed += 1
        if processed % 200 == 0:
            save_progress(done)
            print(f"...进度 {processed} 已处理, {aligned} 改, 用时{time.time()-t0:.0f}s", flush=True)
    save_progress(done)
    print(f"\n完成: 本次处理 {processed}, 打齐 {aligned}, 总用时{time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--reset", action="store_true")
    a = ap.parse_args()
    asyncio.run(main(limit=a.limit, reset=a.reset))
