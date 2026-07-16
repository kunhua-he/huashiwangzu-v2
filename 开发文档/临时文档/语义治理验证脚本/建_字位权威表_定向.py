# -*- coding: utf-8 -*-
"""定向预计算字位权威表:只算"待打齐实体名实际会查的坑位",不穷举整个语料。
华哥:穷举整语料1860万组合是浪费,只需要4万实体名用到的几十万坑位。算法/精度完全不变。

流程:
  ① 从待打齐实体名提取所有 (left,right) 坑位 → 白名单(几十万)
  ② 全语料扫一遍(100秒),滑窗时只保留坑位在白名单里的组合(表缩小50~100倍)
  ③ 写CSV → psql copy 秒级导入
窗口逻辑1:1复刻 semantic_align_service(WIN=2,左右各最多2汉字碰非汉字停),chunk级去重=等价原COUNT(*)。
用法: python 建_字位权威表_定向.py [--owner 4]
"""
import asyncio, sys, time, argparse, csv, os
sys.path.insert(0, "backend"); sys.path.insert(0, ".")
from app.database import AsyncSessionLocal
from sqlalchemy import text as T

WIN = 2
_IMG = "'.jpg','.jpeg','.png','.gif','.bmp','.webp','.tiff','.svg'"


def _is_cjk(ch):
    return bool(ch) and "一" <= ch <= "鿿"


def _cjk_run(chars, start, step, limit):
    out = []
    i = start
    while 0 <= i < len(chars) and len(out) < limit and _is_cjk(chars[i]):
        out.append(chars[i]); i += step
    if step < 0:
        out.reverse()
    return "".join(out)


def _坑位(name):
    """复刻 canonicalize_name 的窗口:对每个汉字位,产出它会查的 (left,right) 坑位。"""
    chars = list(name)
    n = len(chars)
    out = []
    for i in range(n):
        if not _is_cjk(chars[i]):
            continue
        left = _cjk_run(chars, i - 1, -1, WIN)
        right = _cjk_run(chars, i + 1, 1, WIN)
        if left and right:
            out.append((left, right))
    return out


async def 提取白名单(owner):
    """从待打齐实体名提取所有坑位。含变体可能产生的坑位(用原名窗口覆盖绝大多数)。"""
    白 = set()
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(T("""
            SELECT name FROM kb_entity_dictionary
            WHERE owner_id=:o AND status!='merged'
              AND name ~ '[一-鿿]' AND length(name)>=2
        """), {"o": owner})).all()
    for (name,) in rows:
        for lr in _坑位(name):
            白.add(lr)
    return 白, len(rows)


async def main(owner):
    t0 = time.time()
    白名单, 实体数 = await 提取白名单(owner)
    print(f"实体数{实体数}, 白名单坑位{len(白名单)}个 (对比穷举1860万), 用时{time.time()-t0:.0f}s", flush=True)

    # 全语料扫一遍,只统计白名单坑位的中间字分布(chunk级去重)
    统计 = {}
    扫过 = 0; last_id = 0
    while True:
        async with AsyncSessionLocal() as db:
            rows = (await db.execute(T(f"""
                SELECT c.id, c.text FROM kb_chunks c JOIN kb_documents d ON d.id=c.document_id
                WHERE c.owner_id=:o AND c.index_layer='base_parse'
                  AND d.extension NOT IN ({_IMG}) AND c.id > :last
                ORDER BY c.id LIMIT 5000
            """), {"o": owner, "last": last_id})).all()
        if not rows:
            break
        for cid, text in rows:
            if text:
                _滑窗过滤(text, cid, 白名单, 统计)
            last_id = cid
        扫过 += len(rows)
        if 扫过 % 50000 == 0:
            print(f"  扫过{扫过} 命中组合{len(统计)} 用时{time.time()-t0:.0f}s", flush=True)

    print(f"统计完成: {len(统计)}个命中组合, 用时{time.time()-t0:.0f}s. 写CSV...", flush=True)
    csv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"字位权威定向_owner{owner}.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        for (l, r, mid), cnt in 统计.items():
            w.writerow([owner, l, r, mid, cnt])
    print(f"★CSV已写 {csv_path} ({len(统计)}行) 用时{time.time()-t0:.0f}s", flush=True)


def _滑窗过滤(text, cid, 白名单, 统计):
    chars = list(text)
    n = len(chars)
    本chunk = set()
    for i in range(n):
        if not _is_cjk(chars[i]):
            continue
        mid = chars[i]
        lefts = []
        l1 = _cjk_run(chars, i - 1, -1, 1)
        l2 = _cjk_run(chars, i - 1, -1, 2)
        if l1: lefts.append(l1)
        if len(l2) == 2 and l2 != l1: lefts.append(l2)
        rights = []
        r1 = _cjk_run(chars, i + 1, 1, 1)
        r2 = _cjk_run(chars, i + 1, 1, 2)
        if r1: rights.append(r1)
        if len(r2) == 2 and r2 != r1: rights.append(r2)
        for l in lefts:
            for r in rights:
                if (l, r) in 白名单:  # 只统计待打齐实体会查的坑位
                    key = (l, r, mid)
                    if key not in 本chunk:
                        本chunk.add(key)
                        统计[key] = 统计.get(key, 0) + 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--owner", type=int, default=4)
    a = ap.parse_args()
    asyncio.run(main(a.owner))
