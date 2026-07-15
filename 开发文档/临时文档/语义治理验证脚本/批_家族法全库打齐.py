# -*- coding: utf-8 -*-
"""全库语义打齐(家族法,高效)。字典分组定位变体家族→每家族一次文本层权威查询→合并。

原理:同类别同长度、只差一个字位的实体=变体家族。分组已知"哪位在变",所以每家族只需
      一次"该位权威字"查询(用家族完整前后缀,长上下文触发trgm索引,快)。
安全:改后完整名必须在干净文本层逐字命中≥1篇(护栏);权威字须碾压且是汉字。
全自动、零LLM、可断点续(进度落盘)。owner=4。用法: python 批_家族法全库打齐.py [--limit N] [--reset] [--dry]
"""
import asyncio, sys, time, json, os, argparse
from collections import defaultdict
sys.path.insert(0, "backend"); sys.path.insert(0, ".")
from app.database import AsyncSessionLocal
from sqlalchemy import text as T
from modules.knowledge.backend.services.semantic_align_service import (
    _slot_authority, _name_attested, _is_cjk, _resolve_canonical_entity,
    _merge_variant_into, AUTH_RATIO, AUTH_MIN,
)

OWNER = 4
PROGRESS = "/tmp/家族打齐进度.json"


async def load_families(db):
    """加载实体→Python分组→返回变体家族列表 [(prefix,suffix,pos,[(id,name,cat)...])]。"""
    r = await db.execute(T("""
        SELECT DISTINCT ed.id, ed.name, ed.category
        FROM kb_chunk_entities ce JOIN kb_entity_dictionary ed ON ed.id=ce.entity_id AND ed.owner_id=ce.owner_id
        WHERE ce.owner_id=4 AND ed.status!='merged' AND ed.name ~ '[一-鿿]' AND length(ed.name) BETWEEN 3 AND 24
    """))
    ents = [(int(i), n, c) for i, n, c in r.all()]
    masked = defaultdict(list)
    for eid, name, cat in ents:
        for i in range(len(name)):
            if not _is_cjk(name[i]):
                continue  # 只在汉字位分组
            masked[(cat, len(name), i, name[:i] + "\0" + name[i+1:])].append((eid, name, cat))
    families = []
    for (cat, L, pos, mstr), members in masked.items():
        if len(members) < 2:
            continue
        prefix, suffix = mstr[:pos], mstr[pos+1:]
        families.append((prefix, suffix, pos, members))
    # 短上下文(慢)排后面,长上下文(trgm快)先跑,早出成果
    families.sort(key=lambda f: -(len(f[0]) + len(f[1])))
    return families


async def resolve_family(db, prefix, suffix, members):
    """定这家族的权威字+规范名。返回 (canonical_name, auth_char, ev, second, ranked_map) 或 None。"""
    if not prefix or not suffix:
        return None  # 护栏:句首/句尾单边空
    ranked = await _slot_authority(db, OWNER, prefix, suffix)
    if not ranked:
        return None
    top_ch, top_n = ranked[0]
    second = ranked[1][1] if len(ranked) > 1 else 0
    if not _is_cjk(top_ch):
        return None
    if top_n < max(AUTH_MIN, second * AUTH_RATIO):
        return None
    canonical_name = prefix + top_ch + suffix
    if await _name_attested(db, OWNER, canonical_name) < 1:
        return None  # 终极护栏:改后名文本层查无此串→驳回
    return canonical_name, top_ch, top_n, second, dict(ranked)


def load_done():
    if os.path.exists(PROGRESS):
        try: return set(json.load(open(PROGRESS)))
        except Exception: return set()
    return set()


async def main(limit=None, reset=False, dry=False):
    if reset and os.path.exists(PROGRESS):
        os.remove(PROGRESS)
    done = load_done()
    async with AsyncSessionLocal() as db:
        families = await load_families(db)
    print(f"变体家族 {len(families)} 个, 已处理 {len(done)}", flush=True)
    processed = merged_total = fam_hit = 0
    t0 = time.time()
    for prefix, suffix, pos, members in families:
        fam_key = f"{prefix}\0{suffix}\0{pos}"
        if fam_key in done:
            continue
        if limit and processed >= limit:
            break
        processed += 1
        try:
            async with AsyncSessionLocal() as db:
                res = await resolve_family(db, prefix, suffix, members)
                if res:
                    canonical_name, auth_ch, ev, second, ranked_map = res
                    cid = await _resolve_canonical_entity(db, OWNER, canonical_name, members[0][2])
                    n_merged = 0
                    for eid, name, cat in members:
                        if name == canonical_name:
                            continue
                        # 护栏4:待并变体的差异字若在该位文本层真实出现≥VALID_MIN→真值,不并
                        if ranked_map.get(name[pos], 0) >= VALID_MIN:
                            continue
                        fixes = [{"pos": pos, "from": name[pos], "to": auth_ch, "evidence": ev, "runner_up": second}]
                        await _merge_variant_into(db, OWNER, eid, name, cid, canonical_name, fixes)
                        n_merged += 1
                    if n_merged:
                        fam_hit += 1
                    if n_merged:
                        if dry:
                            await db.rollback()
                        else:
                            await db.commit()
                        merged_total += n_merged
                        print(f"  [家族{fam_hit}] {prefix}＊{suffix} → 锚[{canonical_name}](权威'{auth_ch}'{ev}块) 并{n_merged}个: {[m[1] for m in members if m[1]!=canonical_name][:5]}", flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f"  !家族[{prefix}＊{suffix}]异常: {str(exc)[:120]}", flush=True)
        done.add(fam_key)
        if processed % 100 == 0:
            if not dry:
                json.dump(sorted(done), open(PROGRESS, "w"))
            print(f"...{processed}家族已过, 命中{fam_hit}, 合并{merged_total}, 用时{time.time()-t0:.0f}s", flush=True)
    if not dry:
        json.dump(sorted(done), open(PROGRESS, "w"))
    print(f"\n完成: 过{processed}家族, 命中{fam_hit}, 合并{merged_total}实体, 用时{time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--reset", action="store_true")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    asyncio.run(main(limit=a.limit, reset=a.reset, dry=a.dry))
