# -*- coding: utf-8 -*-
"""建字位权威预计算表 kb_char_slot_authority。根治 _slot_authority 全表正则扫。"""
import asyncio, sys
sys.path.insert(0, "backend"); sys.path.insert(0, ".")
from app.database import AsyncSessionLocal
from sqlalchemy import text as T

DDL = """
CREATE TABLE IF NOT EXISTS kb_char_slot_authority(
    owner_id  INTEGER NOT NULL,
    left_ctx  VARCHAR NOT NULL,
    right_ctx VARCHAR NOT NULL,
    mid_char  VARCHAR NOT NULL,
    cnt       INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (owner_id, left_ctx, right_ctx, mid_char)
)
"""
IDX = """
CREATE INDEX IF NOT EXISTS idx_char_slot_lookup
ON kb_char_slot_authority (owner_id, left_ctx, right_ctx)
"""


async def m():
    async with AsyncSessionLocal() as db:
        await db.execute(T(DDL))
        await db.execute(T(IDX))
        await db.commit()
        print("kb_char_slot_authority 建表+索引完成")


if __name__ == "__main__":
    asyncio.run(m())
