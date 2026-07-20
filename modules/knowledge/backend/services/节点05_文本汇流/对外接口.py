# -*- coding: utf-8 -*-
"""节点⑤ 唯一对外接口。

函数：汇流(db, document_id, owner_id, page=None) -> dict
只读 kb_raw_data，按页汇总 text/ocr/vision/vision_desc。
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .分round归位 import 组页字典, 页状态

logger = logging.getLogger("v2.knowledge.node05")

_SQL_DOC = """
SELECT id, page, round, source_type, content, metadata_json, status
FROM kb_raw_data
WHERE document_id = :d AND owner_id = :o
ORDER BY page, round, id
"""

_SQL_PAGE = """
SELECT id, page, round, source_type, content, metadata_json, status
FROM kb_raw_data
WHERE document_id = :d AND owner_id = :o AND page = :p
ORDER BY round, id
"""


def _row_to_dict(row: Any) -> dict[str, Any]:
    mapping = row._mapping if hasattr(row, "_mapping") else row
    return {
        "id": mapping["id"],
        "page": mapping["page"],
        "round": mapping["round"],
        "source_type": mapping["source_type"],
        "content": mapping["content"],
        "metadata_json": mapping["metadata_json"],
        "status": mapping["status"],
    }


async def 汇流(
    db: AsyncSession,
    document_id: int,
    owner_id: int,
    page: int | None = None,
) -> dict[str, Any]:
    """统一读三路 raw。page=None 返回整文档 pages 字典。"""
    doc_id = int(document_id)
    oid = int(owner_id)
    if page is None:
        result = await db.execute(text(_SQL_DOC), {"d": doc_id, "o": oid})
        rows = [_row_to_dict(r) for r in result.fetchall()]
        pages = 组页字典(rows)
        for 槽 in pages.values():
            槽["status"] = 页状态(槽)
        if not pages:
            status = "empty"
        elif all(p.get("status") == "ok" for p in pages.values()):
            status = "ok"
        else:
            status = "partial"
        logger.info(
            "node05 汇流 document_id=%s owner_id=%s pages=%s status=%s",
            doc_id,
            oid,
            len(pages),
            status,
        )
        return {
            "document_id": doc_id,
            "owner_id": oid,
            "status": status,
            "page_count": len(pages),
            "pages": pages,
        }

    page_no = int(page)
    result = await db.execute(text(_SQL_PAGE), {"d": doc_id, "o": oid, "p": page_no})
    rows = [_row_to_dict(r) for r in result.fetchall()]
    pages = 组页字典(rows)
    槽 = pages.get(page_no) or {
        "page": page_no,
        "text": "",
        "ocr": "",
        "vision": "",
        "vision_desc": "",
        "vision_desc_source": "round3_content",
        "text_id": None,
        "ocr_id": None,
        "vision_id": None,
        "text_status": None,
        "ocr_status": None,
        "vision_status": None,
        "text_meta": None,
        "ocr_meta": None,
        "vision_meta": None,
        "evidence_ids": [],
        "round_texts": {},
    }
    槽["status"] = 页状态(槽)
    logger.info(
        "node05 汇流 document_id=%s page=%s status=%s",
        doc_id,
        page_no,
        槽["status"],
    )
    return {
        "document_id": doc_id,
        "owner_id": oid,
        "page": page_no,
        **槽,
    }


# 英文兼容别名
converge_text_layers = 汇流
