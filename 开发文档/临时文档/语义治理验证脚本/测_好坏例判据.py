# -*- coding: utf-8 -*-
"""实测好例(该合并)vs坏例(误伤)的信号差异,找准判据。owner=4。"""
import asyncio, sys
sys.path.insert(0, "backend"); sys.path.insert(0, ".")
from app.database import AsyncSessionLocal
from modules.knowledge.backend.services.semantic_align_service import _slot_authority, _name_attested, _cjk_run, _is_cjk, WIN

# (原名, 改后名, 变化位) —— 好例该合并,坏例是误伤
GOOD = [("华世王族集团","华世王镞集团",3),("娇巢诗","娇薇诗",1),("苏雯雅","苏蜜雅",1),("华世王璞公司","华世王镞公司",3)]
BAD  = [("超补水","超纯水",1),("透明肌","透美肌",1),("养胃粥","养生粥",1),("圣斗士","圣痘士",1),("按压瓶","按单瓶",2),("治闭口","治路口",1),("抗衰感","抗敏感",1)]

async def probe(db, name, fixed, pos):
    chars=list(name)
    left=_cjk_run(chars,pos-1,-1,WIN); right=_cjk_run(chars,pos+1,1,WIN)
    ranked=await _slot_authority(db,4,left,right)
    rmap=dict(ranked)
    auth_ch=fixed[pos]; orig_ch=name[pos]
    auth_n=rmap.get(auth_ch,0); orig_n=rmap.get(orig_ch,0)
    orig_att=await _name_attested(db,4,name)      # 原名文本层篇数
    fixed_att=await _name_attested(db,4,fixed)     # 改后名文本层篇数
    print(f"  {name}→{fixed} | 窗口[{left}X{right}] 权威{auth_ch}={auth_n} 原字{orig_ch}={orig_n} | 原名命中{orig_att}篇 改后命中{fixed_att}篇")

async def m():
    async with AsyncSessionLocal() as db:
        print("=== 好例(该合并) ===")
        for n,f,p in GOOD: await probe(db,n,f,p)
        print("=== 坏例(误伤) ===")
        for n,f,p in BAD: await probe(db,n,f,p)

if __name__=="__main__":
    asyncio.run(m())
