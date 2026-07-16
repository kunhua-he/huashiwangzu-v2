# -*- coding: utf-8 -*-
"""生成 owner=4 admin 的有效 JWT(带正确 session_version)。调度器调用。"""
import asyncio, sys
sys.path.insert(0, "backend"); sys.path.insert(0, ".")
from app.services.auth import create_access_token, get_user_by_id
from app.database import AsyncSessionLocal


async def m():
    async with AsyncSessionLocal() as db:
        u = await get_user_by_id(db, 4)
        sv = getattr(u, "session_version", 0) if u else 0
    print(create_access_token(4, "admin", sv))


if __name__ == "__main__":
    asyncio.run(m())
