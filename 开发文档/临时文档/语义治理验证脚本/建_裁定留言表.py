# -*- coding: utf-8 -*-
"""建实体裁定留言表 kb_entity_verdict_review。
证据驱动裁定小agent:高置信直接执行,低置信/证据不足→留言进此表待华哥复核(不写死DB)。
"""
import asyncio, sys
sys.path.insert(0, "backend"); sys.path.insert(0, ".")
from app.database import AsyncSessionLocal
from sqlalchemy import text as T

DDL = """
CREATE TABLE IF NOT EXISTS kb_entity_verdict_review(
    id BIGSERIAL PRIMARY KEY,
    owner_id INTEGER NOT NULL,
    entity_id BIGINT,
    orig_name VARCHAR NOT NULL,
    cand_name VARCHAR NOT NULL,
    verdict VARCHAR NOT NULL,
    confidence REAL,
    agent_note TEXT,
    evidence_json JSONB,
    judged_by VARCHAR,
    review_status VARCHAR DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(owner_id, orig_name, cand_name)
)
"""


async def m():
    async with AsyncSessionLocal() as db:
        await db.execute(T(DDL))
        await db.commit()
        print("kb_entity_verdict_review 建表完成")


if __name__ == "__main__":
    asyncio.run(m())
