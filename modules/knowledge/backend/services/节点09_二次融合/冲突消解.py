# -*- coding: utf-8 -*-
"""冲突消解：检测同主体跨文档矛盾，只标记不自动解决。"""
from __future__ import annotations

import json
from typing import Any


def _sig(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def 消解冲突(
    聚合结果: dict[str, Any],
) -> dict[str, Any]:
    """基于 attributes_by_source 产出 conflicts 列表。

    返回 {conflicts: [...], conflict_count}
    每条 conflict: {field, values:[{document_id,page,value}], status:open}
    """
    by_source = 聚合结果.get("attributes_by_source") or {}
    conflicts: list[dict[str, Any]] = []
    if not isinstance(by_source, dict):
        return {"conflicts": [], "conflict_count": 0}

    for field, entries in by_source.items():
        if not isinstance(entries, list) or len(entries) < 2:
            continue
        buckets: dict[str, list[dict[str, Any]]] = {}
        for e in entries:
            if not isinstance(e, dict):
                continue
            buckets.setdefault(_sig(e.get("value")), []).append(
                {
                    "document_id": e.get("document_id"),
                    "page": e.get("page"),
                    "value": e.get("value"),
                }
            )
        if len(buckets) <= 1:
            continue
        values = []
        for items in buckets.values():
            rep = dict(items[0])
            rep["count"] = len(items)
            values.append(rep)
        conflicts.append(
            {
                "field": str(field),
                "values": values,
                "status": "open",
                "detail": f"字段 {field} 存在 {len(buckets)} 种跨文档取值",
            }
        )

    return {
        "conflicts": conflicts,
        "conflict_count": len(conflicts),
    }
