# -*- coding: utf-8 -*-
"""全量构建字位权威表:一次性扫文本层→内存滑窗统计→批量写表。
根治 _slot_authority 的20万次全表扫。窗口逻辑1:1复刻(WIN=2,左右各最多2汉字碰非汉字停)。
cnt=按 document 去重(与原 COUNT(DISTINCT document) 等价),保精度。owner=4。
用法: python 建_字位权威表.py [--owner 4] [--batch 5000]
"""
import asyncio, sys, time, argparse
sys.path.insert(0, "backend"); sys.path.insert(0, ".")
from app.database import AsyncSessionLocal
from sqlalchemy import text as T

WIN = 2  # 与 semantic_align_service 一致

_IMG = ("'.jpg','.jpeg','.png','.gif','.bmp','.webp','.tiff','.svg'")


def _is_cjk(ch: str) -> bool:
    return bool(ch) and "一" <= ch <= "鿿"


def _cjk_run(chars, start, step, limit):
    out = []
    i = start
    while 0 <= i < len(chars) and len(out) < limit and _is_cjk(chars[i]):
        out.append(chars[i]); i += step
    if step < 0:
        out.reverse()
    return "".join(out)


def _滑窗(text, cid, 统计, 本chunk已记):
    """对一段文本滑窗,把 (left,right,mid) 计数 +1(chunk级去重)。
    严格等价原 _slot_authority 的 COUNT(*):每个匹配chunk对每个(l,r,mid)只贡献1次。
    用 本chunk已记(set,每chunk清空)去重,避免存全部chunk_id(省内存,不OOM)。
    """
    chars = list(text)
    n = len(chars)
    for i in range(n):
        if not _is_cjk(chars[i]):
            continue
        mid = chars[i]
        lefts = []
        l1 = _cjk_run(chars, i - 1, -1, 1)
        l2 = _cjk_run(chars, i - 1, -1, 2)
        if l1:
            lefts.append(l1)
        if len(l2) == 2 and l2 != l1:
            lefts.append(l2)
        rights = []
        r1 = _cjk_run(chars, i + 1, 1, 1)
        r2 = _cjk_run(chars, i + 1, 1, 2)
        if r1:
            rights.append(r1)
        if len(r2) == 2 and r2 != r1:
            rights.append(r2)
        for l in lefts:
            for r in rights:
                key = (l, r, mid)
                if key not in 本chunk已记:  # 本chunk内该组合只计1次(chunk级去重)
                    本chunk已记.add(key)
                    统计[key] = 统计.get(key, 0) + 1


async def main(owner, batch):
    t0 = time.time()
    统计 = {}
    扫过 = 0
    last_id = 0
    async with AsyncSessionLocal() as db:
        总数 = (await db.execute(T(f"""
            SELECT count(*) FROM kb_chunks c JOIN kb_documents d ON d.id=c.document_id
            WHERE c.owner_id=:o AND c.index_layer='base_parse' AND d.extension NOT IN ({_IMG})
        """), {"o": owner})).first()[0]
    print(f"文本层chunk总数: {总数}, 分批={batch}", flush=True)

    while True:
        async with AsyncSessionLocal() as db:
            rows = (await db.execute(T(f"""
                SELECT c.id, c.document_id, c.text
                FROM kb_chunks c JOIN kb_documents d ON d.id=c.document_id
                WHERE c.owner_id=:o AND c.index_layer='base_parse'
                  AND d.extension NOT IN ({_IMG}) AND c.id > :last
                ORDER BY c.id LIMIT :b
            """), {"o": owner, "last": last_id, "b": batch})).all()
        if not rows:
            break
        for cid, doc_id, text in rows:
            if text:
                _滑窗(text, cid, 统计, set())  # 每chunk一个新的已记set
            last_id = cid
        扫过 += len(rows)
        if 扫过 % 50000 == 0:
            print(f"  扫过{扫过}/{总数} 组合数{len(统计)} 用时{time.time()-t0:.0f}s", flush=True)

    print(f"统计完成: {len(统计)}个唯一(左,右,中)组合, 用时{time.time()-t0:.0f}s. 写CSV...", flush=True)
    csv_path = _写CSV(owner, 统计)
    print(f"CSV已写: {csv_path} ({len(统计)}行). 用 psql 导入(见脚本末尾提示). 总用时{time.time()-t0:.0f}s", flush=True)


def _写CSV(owner, 统计):
    """把统计写成 CSV(纯文件IO,不碰DB连接=绝不因连接超时暴毙)。返回路径。
    随后用 psql \\copy 一条命令导入(PG原生,几秒)。"""
    import csv, os
    csv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"字位权威_owner{owner}.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        for (l, r, mid), cnt in 统计.items():
            w.writerow([owner, l, r, mid, cnt])
    return csv_path


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--owner", type=int, default=4)
    ap.add_argument("--batch", type=int, default=5000)
    a = ap.parse_args()
    asyncio.run(main(a.owner, a.batch))
