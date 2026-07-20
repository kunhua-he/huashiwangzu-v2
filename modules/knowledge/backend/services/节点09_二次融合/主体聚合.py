# -*- coding: utf-8 -*-
"""主体聚合：同主体跨文档信息聚合成视图（纯 DB，不烧 LLM）。"""
from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("v2.knowledge.node09.聚合")

_SQL_ENTITY = """
SELECT id, name, type_id, category, status, canonical_id
FROM kb_entity_dictionary
WHERE owner_id = :o AND id = :e
LIMIT 1
"""

_SQL_PAGES = """
SELECT
  docs.document_id,
  pf.page,
  pf.id AS page_fusion_id,
  pf.fused_text,
  pf.page_summary,
  pf.page_title,
  pf.attributes_json,
  pf.body_json,
  pf.confidence
FROM (
  SELECT DISTINCT ce.document_id
  FROM kb_chunk_entities ce
  JOIN kb_entity_dictionary ed
    ON ed.id = ce.entity_id AND ed.owner_id = ce.owner_id
  WHERE ce.owner_id = :o
    AND COALESCE(ed.canonical_id, ed.id) = :anchor
    AND (ed.status IS NULL OR ed.status <> 'merged' OR ed.id = :anchor)
) docs
LEFT JOIN kb_page_fusions pf
  ON pf.document_id = docs.document_id
 AND pf.owner_id = :o
 AND pf.fusion_status IN ('done', 'completed', 'ok')
ORDER BY docs.document_id, pf.page NULLS LAST
LIMIT 2000
"""


def _as_dict(val: Any) -> dict[str, Any]:
    if isinstance(val, dict):
        return val
    if isinstance(val, str) and val.strip():
        try:
            parsed = json.loads(val)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def _as_list(val: Any) -> list[Any]:
    if isinstance(val, list):
        return val
    if isinstance(val, str) and val.strip():
        try:
            parsed = json.loads(val)
            return parsed if isinstance(parsed, list) else []
        except Exception:
            return []
    return []


def _content_hash(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


async def 聚合主体(
    db: AsyncSession,
    entity_id: int,
    owner_id: int,
) -> dict[str, Any]:
    """按 entity_id（canonical 归一）聚合跨文档页属性。"""
    eid = int(entity_id)
    oid = int(owner_id)
    ent = (await db.execute(text(_SQL_ENTITY), {"o": oid, "e": eid})).mappings().first()
    if not ent:
        return {"status": "empty", "entity_id": eid, "owner_id": oid, "reason": "entity_not_found"}

    anchor = int(ent["canonical_id"] or ent["id"])
    if anchor != eid:
        # 若传入的是变体，锚到 canonical
        anchor_row = (
            await db.execute(text(_SQL_ENTITY), {"o": oid, "e": anchor})
        ).mappings().first()
        if anchor_row:
            ent = anchor_row

    rows = (
        await db.execute(text(_SQL_PAGES), {"o": oid, "anchor": anchor})
    ).mappings().all()

    attributes: dict[str, list[dict[str, Any]]] = {}
    evidence: list[dict[str, Any]] = []
    doc_ids: set[int] = set()
    page_keys: set[tuple[int, int]] = set()
    claims: list[dict[str, Any]] = []

    for row in rows:
        doc_id = int(row["document_id"])
        doc_ids.add(doc_id)
        page = row["page"]
        if page is not None:
            page_keys.add((doc_id, int(page)))
        attrs = _as_dict(row["attributes_json"])
        body = _as_list(row["body_json"])
        if attrs:
            for key, value in attrs.items():
                if key.startswith("_"):
                    continue
                entry = {
                    "document_id": doc_id,
                    "page": int(page) if page is not None else None,
                    "page_fusion_id": int(row["page_fusion_id"]) if row["page_fusion_id"] else None,
                    "value": value,
                }
                attributes.setdefault(str(key), []).append(entry)
                claims.append({"field": str(key), **entry})
        if row["page_fusion_id"]:
            evidence.append(
                {
                    "document_id": doc_id,
                    "page": int(page) if page is not None else None,
                    "page_fusion_id": int(row["page_fusion_id"]),
                    "page_title": row["page_title"],
                    "page_summary": (row["page_summary"] or "")[:240] if row["page_summary"] else None,
                    "body_entity_count": len(body),
                    "confidence": row["confidence"],
                }
            )

    # 合并同值
    merged_attrs: dict[str, Any] = {}
    for key, entries in attributes.items():
        values = []
        seen_v = set()
        for e in entries:
            v = e.get("value")
            sig = json.dumps(v, ensure_ascii=False, sort_keys=True, default=str)
            if sig in seen_v:
                continue
            seen_v.add(sig)
            values.append(v)
        if len(values) == 1:
            merged_attrs[key] = values[0]
        elif values:
            # 多值先保留众数式：出现最多的规范化值
            from collections import Counter

            cnt = Counter(
                json.dumps(e.get("value"), ensure_ascii=False, sort_keys=True, default=str)
                for e in entries
            )
            top_sig, _ = cnt.most_common(1)[0]
            for e in entries:
                if json.dumps(e.get("value"), ensure_ascii=False, sort_keys=True, default=str) == top_sig:
                    merged_attrs[key] = e.get("value")
                    break

    view_core = {
        "entity_id": anchor,
        "entity_name": ent["name"],
        "type_id": ent["type_id"],
        "category": ent["category"],
        "attributes": merged_attrs,
        "source_document_ids": sorted(doc_ids),
        "page_count": len(page_keys),
        "document_count": len(doc_ids),
    }
    status = "ok" if doc_ids else "empty"
    result = {
        "status": status,
        "owner_id": oid,
        "entity_id": anchor,
        "requested_entity_id": eid,
        "entity_name": ent["name"],
        "type_id": ent["type_id"],
        "category": ent["category"],
        "attributes": merged_attrs,
        "attributes_by_source": attributes,
        "claims": claims,
        "evidence": evidence[:500],
        "source_document_ids": sorted(doc_ids),
        "page_count": len(page_keys),
        "document_count": len(doc_ids),
        "content_hash": _content_hash(view_core),
    }
    logger.info(
        "聚合主体 entity=%s docs=%s pages=%s attrs=%s",
        anchor,
        len(doc_ids),
        len(page_keys),
        len(merged_attrs),
    )
    return result
