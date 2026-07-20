# -*- coding: utf-8 -*-
"""关联文档发现：新文档经共享实体找旧文档。"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("v2.knowledge.node10.发现")

# 新文档实体锚点 → 其他文档共现
_SQL = """
WITH src AS (
  SELECT DISTINCT COALESCE(ed.canonical_id, ed.id) AS entity_id
  FROM kb_chunk_entities ce
  JOIN kb_entity_dictionary ed
    ON ed.id = ce.entity_id AND ed.owner_id = ce.owner_id
  WHERE ce.document_id = :d
    AND ce.owner_id = :o
    AND (ed.status IS NULL OR ed.status <> 'merged' OR ed.id = COALESCE(ed.canonical_id, ed.id))
),
hits AS (
  SELECT
    ce.document_id AS related_document_id,
    COALESCE(ed.canonical_id, ed.id) AS entity_id,
    MAX(ed.name) AS entity_name,
    COUNT(*) AS shared_hit
  FROM kb_chunk_entities ce
  JOIN kb_entity_dictionary ed
    ON ed.id = ce.entity_id AND ed.owner_id = ce.owner_id
  JOIN src ON src.entity_id = COALESCE(ed.canonical_id, ed.id)
  WHERE ce.owner_id = :o
    AND ce.document_id <> :d
  GROUP BY ce.document_id, COALESCE(ed.canonical_id, ed.id)
)
SELECT related_document_id, entity_id, entity_name, shared_hit
FROM hits
ORDER BY shared_hit DESC, related_document_id
LIMIT 500
"""


async def 发现关联文档(
    db: AsyncSession,
    document_id: int,
    owner_id: int,
) -> dict[str, Any]:
    doc_id = int(document_id)
    oid = int(owner_id)
    rows = (await db.execute(text(_SQL), {"d": doc_id, "o": oid})).mappings().all()
    related: dict[int, dict[str, Any]] = {}
    for row in rows:
        rid = int(row["related_document_id"])
        bucket = related.setdefault(
            rid,
            {
                "document_id": rid,
                "shared_entities": [],
                "shared_entity_count": 0,
                "shared_hit": 0,
            },
        )
        bucket["shared_entities"].append(
            {
                "entity_id": int(row["entity_id"]),
                "entity_name": row["entity_name"],
                "hit": int(row["shared_hit"] or 0),
            }
        )
        bucket["shared_entity_count"] = len(bucket["shared_entities"])
        bucket["shared_hit"] += int(row["shared_hit"] or 0)

    items = sorted(related.values(), key=lambda x: (-x["shared_hit"], x["document_id"]))
    logger.info("发现关联文档 new=%s related=%s", doc_id, len(items))
    return {
        "status": "ok" if items else "empty",
        "document_id": doc_id,
        "owner_id": oid,
        "related_documents": items,
        "related_count": len(items),
    }
