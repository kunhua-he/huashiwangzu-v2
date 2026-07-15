# -*- coding: utf-8 -*-
"""清洗实体词典的技术噪音(VLM越界/像素/管线伪影抽出的假实体)。纯规则、免费、可回溯。

标 status='archived'(召回只认 candidate/confirmed,自动排除;不删数据,semantic_meta留原因可回滚)。
噪音判据(普适非行业):图片格式/像素尺寸/色彩空间/VLM轮次标记/视觉分析术语。owner=4。
用法: python 清_技术噪音实体.py [--go]  (默认dry只统计,--go才写)
"""
import asyncio, sys, json, argparse
sys.path.insert(0, "backend"); sys.path.insert(0, ".")
from app.database import AsyncSessionLocal
from sqlalchemy import text as T

OWNER = 4
# 普适技术噪音正则(图片格式/像素/色彩/VLM伪影),不含任何行业词
NOISE_RE = r"(jpeg|jpg|png|gif|webp|bmp|tiff|rgba?|cmyk|photo_like|blank_like|dpi|exif|" \
           r"#[0-9a-f]{3,6}|第[123一二三]轮|视觉构成|视觉轮廓|平均亮度|边缘密度|色彩空间|" \
           r"published body|本地图片分析|截图\s*ocr)"
DIM_RE = r"[0-9]{2,4}\s*x\s*[0-9]{2,4}\s*(px)?"  # 像素尺寸如 5168x3448px


async def main(go=False):
    async with AsyncSessionLocal() as db:
        # 命中噪音的实体
        r = await db.execute(T(f"""
            SELECT id, name, category,
              (SELECT count(*) FROM kb_chunk_entities ce WHERE ce.entity_id=ed.id AND ce.owner_id={OWNER}) AS blk
            FROM kb_entity_dictionary ed
            WHERE owner_id={OWNER} AND status != 'merged' AND status != 'archived'
              AND (name ~* :nre OR name ~ :dre)
            ORDER BY blk DESC
        """), {"nre": NOISE_RE, "dre": DIM_RE})
        rows = r.all()
        print(f"命中技术噪音实体: {len(rows)}, 涉及chunk块合计: {sum(x[3] for x in rows)}")
        print("=== 前20(确认全是噪音) ===")
        for x in rows[:20]:
            print(f"  [{x[1]}]({x[2]},{x[3]}块)")
        if not go:
            print("\n(dry模式,加 --go 才写库标archived)")
            return
        ids = [int(x[0]) for x in rows]
        # 分批标 archived + 留原因
        BATCH = 500
        for i in range(0, len(ids), BATCH):
            chunk = ids[i:i+BATCH]
            await db.execute(T("""
                UPDATE kb_entity_dictionary
                SET status='archived',
                    semantic_meta=CAST(:m AS json),
                    updated_at=now()
                WHERE owner_id=:o AND id = ANY(:ids)
            """), {"o": OWNER, "ids": chunk,
                   "m": json.dumps({"归档原因": "技术噪音(VLM越界/像素/管线伪影)", "可回滚": True}, ensure_ascii=False)})
            await db.commit()
        print(f"\n已标 archived: {len(ids)} 个技术噪音实体(召回自动排除,可回滚)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--go", action="store_true")
    a = ap.parse_args()
    asyncio.run(main(a.go))
