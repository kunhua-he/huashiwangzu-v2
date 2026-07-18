# -*- coding: utf-8 -*-
"""节点⑦ 唯一对外接口。

函数：串联(db, document_id, owner_id) -> dict
返回：entities_found / relationships_found / typed / pending_review / merged / 样例 等

graph 阶段只调本接口（或包级 串联），不许 import 子文件。

流程：
1. 实体抽取（LLM，name+type_name+confidence 一次出）
2. 分类落库（type_id + 图谱/证据）
3. 同文档归并（字级权威）
4. 文档摘要（可选增强，失败不拖垮）
5. 认知索引（可选增强，失败不拖垮）

失败不拖垮：单步异常只记该项。
"""
from __future__ import annotations

import logging
from time import perf_counter
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from .实体分类落库 import 分类落库
from .实体归并 import 同文档归并
from .实体抽取 import 抽取文档融合页
from .文档摘要 import 生成摘要
from .认知索引 import 建认知索引

logger = logging.getLogger("v2.knowledge.node07")


async def 串联(
    db: AsyncSession,
    document_id: int,
    owner_id: int,
    *,
    做摘要: bool = False,
    做认知索引: bool = False,
) -> dict[str, Any]:
    """文档级串联：抽取 → 分类落库 → 归并 →（可选）摘要/认知索引。

    默认不做摘要/认知索引：DAG 已有独立 profile / cognitive_index 阶段，
    避免 graph 阶段重复烧 LLM。自测或离线批处理可显式打开。
    """
    t0 = perf_counter()
    统计: dict[str, Any] = {
        "document_id": int(document_id),
        "owner_id": int(owner_id),
        "entities_found": 0,
        "relationships_found": 0,
        "typed": 0,
        "pending_review": 0,
        "merged": 0,
        "status": "ok",
        "errors": [],
        "样例": [],
    }

    # 1) 抽取
    try:
        抽 = await 抽取文档融合页(db, int(document_id), int(owner_id))
        统计["processed_pages"] = 抽.get("processed_pages", 0)
        统计["page_durations_ms"] = 抽.get("page_durations_ms") or {}
        if 抽.get("model_degraded"):
            统计["model_degraded"] = True
        统计["errors"].extend(抽.get("errors") or [])
        entities = 抽.get("entities") or []
        relationships = 抽.get("relationships") or []
    except Exception as exc:  # noqa: BLE001
        logger.warning("文档 %s 节点⑦抽取失败: %s", document_id, exc)
        统计["status"] = "degraded"
        统计["errors"].append(f"extract:{exc}"[:200])
        统计["reason"] = "entity_extraction_failed"
        统计["timing"] = {"stage_wall_ms": round((perf_counter() - t0) * 1000)}
        return 统计

    if not entities and 统计["errors"]:
        统计["status"] = "degraded"
        统计["reason"] = "entity_extraction_failed"
        统计["timing"] = {"stage_wall_ms": round((perf_counter() - t0) * 1000)}
        return 统计

    # 2) 分类落库
    try:
        落 = await 分类落库(
            db,
            int(document_id),
            int(owner_id),
            entities,
            relationships,
            page_model_used=抽.get("page_model_used") or {},
            page_model_diagnostics=抽.get("page_model_diagnostics") or {},
        )
        统计["entities_found"] = int(落.get("entities_found") or 0)
        统计["relationships_found"] = int(落.get("relationships_found") or 0)
        统计["typed"] = int(落.get("typed") or 0)
        统计["pending_review"] = int(落.get("pending_review") or 0)
        统计["样例"] = 落.get("样例") or []
        统计["cleanup_ms"] = 落.get("cleanup_ms")
        统计["errors"].extend(落.get("errors") or [])
    except Exception as exc:  # noqa: BLE001
        logger.warning("文档 %s 节点⑦落库失败: %s", document_id, exc)
        统计["status"] = "degraded"
        统计["errors"].append(f"classify:{exc}"[:200])
        统计["reason"] = "entity_write_failed"
        统计["timing"] = {"stage_wall_ms": round((perf_counter() - t0) * 1000)}
        return 统计

    # 3) 归并
    try:
        并 = await 同文档归并(db, int(document_id), int(owner_id))
        统计["merged"] = int(并.get("merged") or 0)
        统计["merge_checked"] = int(并.get("checked") or 0)
        统计["merge_details"] = (并.get("details") or [])[:20]
    except Exception as exc:  # noqa: BLE001
        logger.warning("文档 %s 节点⑦归并失败(不拖垮): %s", document_id, exc)
        统计["merge_error"] = str(exc)[:120]

    # 4) 摘要（可选）
    if 做摘要:
        try:
            统计["profile"] = await 生成摘要(db, int(document_id), int(owner_id))
        except Exception as exc:  # noqa: BLE001
            统计["profile_error"] = str(exc)[:120]

    # 5) 认知索引（可选）
    if 做认知索引:
        try:
            统计["cognitive"] = await 建认知索引(db, int(document_id), int(owner_id))
        except Exception as exc:  # noqa: BLE001
            统计["cognitive_error"] = str(exc)[:120]

    if 统计["entities_found"] == 0 and 统计["processed_pages"] and 统计["errors"]:
        统计["status"] = "degraded"
        统计["reason"] = "entity_extraction_failed"

    统计["timing"] = {
        "stage_wall_ms": round((perf_counter() - t0) * 1000),
        "processed_pages": 统计.get("processed_pages", 0),
        "page_durations_ms": 统计.get("page_durations_ms") or {},
    }
    logger.info(
        "节点⑦ 文档%s: entities=%s typed=%s pending=%s merged=%s rel=%s",
        document_id,
        统计["entities_found"],
        统计["typed"],
        统计["pending_review"],
        统计["merged"],
        统计["relationships_found"],
    )
    return 统计


# 英文兼容别名
async def process_document_chain(db: AsyncSession, document_id: int, owner_id: int, **kw) -> dict:
    return await 串联(db, document_id, owner_id, **kw)
