# -*- coding: utf-8 -*-
"""裁定灰区：拿不准的进留言表，复用 实体裁定循环。

规则：
- 默认零 LLM：调用方可不开启裁定(只收集灰区统计)
- 开启时：调 实体裁定循环.裁定；True=可改(本节点仍默认不自动改原文，只记「可纠」)
- 低置信/待定：裁定循环自己写 kb_entity_verdict_review
- 失败不拖垮：单条异常只记日志

入参：db, owner_id, 灰区列表
出参：{留言数, 可纠数, 驳回数, 明细}
"""
from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("v2.knowledge.node03.verdict")


async def 处理灰区(
    db: AsyncSession,
    owner_id: int,
    灰区列表: list[dict],
    *,
    启用模型裁定: bool = False,
    上限: int = 30,
) -> dict:
    """处理灰区。默认只计数不烧模型；启用后才调裁定循环。"""
    统计 = {"留言数": 0, "可纠数": 0, "驳回数": 0, "跳过数": 0, "明细": []}
    if not 灰区列表:
        return 统计

    列表 = 灰区列表[: max(0, 上限)]
    if not 启用模型裁定:
        # 零 LLM：全部记为待人工，不调模型、不写库(避免无意义刷表)
        统计["跳过数"] = len(列表)
        统计["明细"] = [
            {
                "原词": g.get("原词"),
                "候选词": g.get("候选词"),
                "status": "deferred_no_llm",
                "路": g.get("路"),
                "page": g.get("page"),
            }
            for g in 列表[:20]
        ]
        return 统计

    try:
        from ..实体裁定循环 import 裁定  # type: ignore
    except Exception:
        try:
            from modules.knowledge.backend.services.实体裁定循环 import 裁定  # type: ignore
        except Exception as exc:  # noqa: BLE001
            logger.warning("导入实体裁定循环失败: %s", exc)
            统计["跳过数"] = len(列表)
            return 统计

    已见: set[tuple[str, str]] = set()
    for g in 列表:
        原词 = (g.get("原词") or "").strip()
        候选词 = (g.get("候选词") or "").strip()
        if not 原词 or not 候选词 or 原词 == 候选词:
            统计["跳过数"] += 1
            continue
        key = (原词, 候选词)
        if key in 已见:
            统计["跳过数"] += 1
            continue
        已见.add(key)
        try:
            ok = await 裁定(db, int(owner_id), 原词, 候选词)
            if ok:
                统计["可纠数"] += 1
                统计["明细"].append({"原词": 原词, "候选词": 候选词, "status": "merge_ok"})
            else:
                # 裁定循环在低置信时已落留言；这里计驳回/待定
                统计["驳回数"] += 1
                统计["留言数"] += 1
                统计["明细"].append({"原词": 原词, "候选词": 候选词, "status": "reject_or_review"})
        except Exception as exc:  # noqa: BLE001
            logger.warning("灰区裁定失败 %s→%s: %s", 原词, 候选词, exc)
            统计["跳过数"] += 1
            统计["明细"].append({"原词": 原词, "候选词": 候选词, "status": "error", "error": str(exc)[:80]})

    return 统计
