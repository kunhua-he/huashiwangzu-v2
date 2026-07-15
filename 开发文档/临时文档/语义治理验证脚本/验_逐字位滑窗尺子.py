# -*- coding: utf-8 -*-
"""验证核心尺子:逐字位滑窗,文本层当权威。单个名字就能自纠,不需兄弟变体。
对每个字位置,遮住它,拿左右窗口去干净文本层查这一位的权威字。
碾压者≠当前字→OCR错,改;干净名每位都一致→不动(安全)。owner_id=4。"""
import asyncio, sys, re
sys.path.insert(0, "backend"); sys.path.insert(0, ".")
from app.database import AsyncSessionLocal
from sqlalchemy import text as T

OWNER=4
IMG_EXT="('jpg','png','jpeg','gif','bmp','webp','tiff','svg')"
WIN=2                 # 左右各取几个字当上下文窗口
AUTH_RATIO=10         # 权威字碾压次高的倍数
AUTH_MIN=5            # 权威字最少文本层块数(证据下限)

def is_cjk(ch):
    """是否汉字(只对汉字做OCR纠错;英文/标点/数字原样保留)。"""
    return bool(ch) and '一'<=ch<='鿿'

async def slot_authority(db, left, right):
    """查 'left + X + right' 里 X 在干净文本层(排图片)的分布。返回 [(字,块数)...] 降序。"""
    if not left and not right:
        return []
    pat=f"{re.escape(left)}(.){re.escape(right)}"
    rex=f"{re.escape(left)}.{re.escape(right)}"
    r=await db.execute(T(f"""
        SELECT substring(c.text from :pat) AS ch, COUNT(*) AS n
        FROM kb_chunks c JOIN kb_documents d ON d.id=c.document_id
        WHERE c.owner_id=:o AND c.index_layer='base_parse'
          AND d.extension NOT IN {IMG_EXT}
          AND c.text ~ (:re)
        GROUP BY substring(c.text from :pat)
    """), {"pat":pat, "re":rex, "o":OWNER})
    rows=[(ch,n) for ch,n in r.all() if ch and ch.strip()]
    return sorted(rows, key=lambda x:-x[1])

async def canonicalize(db, name):
    """逐字位自纠。返回 (规范名, [改动明细])。改动明细=(位置,原字,权威字,权威块数,次高块数)。"""
    chars=list(name)
    fixes=[]
    for i in range(len(chars)):
        if not is_cjk(chars[i]): continue      # 护栏1:只纠汉字
        # 用当前(可能已修正的)字构造左右窗口,窗口不含 i 位
        left="".join(chars[max(0,i-WIN):i])
        right="".join(chars[i+1:i+1+WIN])
        if not left or not right: continue     # 护栏3:句首/句尾单边空→太松,跳过
        ranked=await slot_authority(db, left, right)
        if not ranked: continue
        top_ch,top_n=ranked[0]; second=ranked[1][1] if len(ranked)>1 else 0
        if top_ch==chars[i]: continue          # 当前字就是权威→不动
        if not is_cjk(top_ch): continue        # 护栏2:不拿标点/字母替换汉字
        if top_n>=max(AUTH_MIN, second*AUTH_RATIO):
            fixes.append((i, chars[i], top_ch, top_n, second))
            chars[i]=top_ch                      # 就地修正,后续窗口用修正后的字
    return "".join(chars), fixes

async def test_one(db, name):
    fixed, fixes = await canonicalize(db, name)
    tag = "改" if fixes else "不动"
    detail = "  ".join(f"位{i}:{o}→{t}({tn}块/次{s})" for i,o,t,tn,s in fixes)
    print(f"[{tag}] {name}  =>  {fixed}   {detail}")

async def main():
    async with AsyncSessionLocal() as db:
        print("=== 已知错字组(应改) ===")
        for n in ["华世王族集团","华世王链集团","华世王嫒集团","华世王旗集团",
                  "云南华世王镁集团","云南华也王镁集团","云南华也王族集团"]:
            await test_one(db, n)
        print("\n=== 已知干净名(应不动) ===")
        for n in ["云南华世王镞集团","华世王镞","华世王镞集团"]:
            await test_one(db, n)
        print("\n=== 随机抽样(看误伤率) ===")
        r=await db.execute(T("""
            SELECT name FROM kb_entity_dictionary
            WHERE owner_id=:o AND status IN ('candidate','confirmed')
              AND category='组织名' AND length(name)>=6
            ORDER BY random() LIMIT 60
        """), {"o":OWNER})
        for (n,) in r.all():
            await test_one(db, n)

if __name__=="__main__":
    asyncio.run(main())
