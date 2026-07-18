# -*- coding: utf-8 -*-
"""回写原文：把纠正结果 UPDATE 回 kb_raw_data.content，留痕写 metadata_json。

规则(铁律)：
- 只改 content + metadata_json，绝不新增列、绝不删行
- metadata_json 写入：
  - 纠错前原文：备份
  - 纠错留痕：{时间, 改动明细, 分支, 路}
- 幂等：若 metadata_json 已有「纠错留痕」且 content 已等于目标 → 跳过
- 若已有留痕但 content 与目标不同：不叠加备份，只更新 content+留痕(防二次污染备份)

入参：db, 纠正项列表
出参：{回写数, 跳过数, 失败数, 明细}
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone

from sqlalchemy import text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("v2.knowledge.node03.writeback")

_留痕键 = "纠错留痕"
_备份键 = "纠错前原文"


def _解析meta(raw) -> dict:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, str):
        try:
            obj = json.loads(raw)
            return obj if isinstance(obj, dict) else {}
        except Exception:  # noqa: BLE001
            return {}
    return {}


def _已纠过(meta: dict) -> bool:
    return isinstance(meta.get(_留痕键), (dict, list))


def _内容哈希(s: str) -> str:
    return hashlib.sha256((s or "").encode("utf-8")).hexdigest()[:32]


async def 回写纠正项(
    db: AsyncSession,
    纠正项列表: list[dict],
    *,
    分支: str = "",
    document_id: int | None = None,
) -> dict:
    """批量回写。每项需 raw_id / 原content / 新content / 改动。"""
    统计 = {"回写数": 0, "跳过数": 0, "失败数": 0, "明细": []}
    if not 纠正项列表:
        return 统计

    for 项 in 纠正项列表:
        raw_id = 项.get("raw_id")
        新 = 项.get("新content") or ""
        原 = 项.get("原content") or ""
        改动 = 项.get("改动") or []
        if not raw_id or not 改动 or 新 == 原:
            统计["跳过数"] += 1
            continue
        try:
            r = await db.execute(
                sa_text(
                    """SELECT id, content, metadata_json, content_hash
                       FROM kb_raw_data WHERE id=:id"""
                ),
                {"id": int(raw_id)},
            )
            row = r.mappings().first()
            if not row:
                统计["失败数"] += 1
                统计["明细"].append({"raw_id": raw_id, "status": "missing"})
                continue

            库content = row["content"] or ""
            meta = _解析meta(row["metadata_json"])

            # 幂等：已有留痕且内容已是纠正结果 → 跳过
            if _已纠过(meta) and 库content == 新:
                统计["跳过数"] += 1
                统计["明细"].append({"raw_id": raw_id, "status": "already_done"})
                continue

            # 已纠过：不叠加备份，只刷新留痕
            if not _已纠过(meta):
                meta[_备份键] = 库content
            meta[_留痕键] = {
                "时间": datetime.now(timezone.utc).isoformat(),
                "document_id": document_id,
                "分支": 分支 or 项.get("分支") or "",
                "路": 项.get("路"),
                "round": 项.get("round"),
                "改动数": len(改动),
                "改动": [
                    {
                        "pos": f.get("pos"),
                        "from": f.get("from"),
                        "to": f.get("to"),
                        "left": f.get("left"),
                        "right": f.get("right"),
                        "evidence": f.get("evidence"),
                    }
                    for f in 改动[:100]
                ],
                "原哈希": _内容哈希(库content),
                "新哈希": _内容哈希(新),
            }

            await db.execute(
                sa_text(
                    """UPDATE kb_raw_data
                       SET content=:c,
                           metadata_json=CAST(:m AS json),
                           content_hash=:h,
                           updated_at=now()
                       WHERE id=:id"""
                ),
                {
                    "c": 新,
                    "m": json.dumps(meta, ensure_ascii=False),
                    "h": _内容哈希(新),
                    "id": int(raw_id),
                },
            )
            统计["回写数"] += 1
            统计["明细"].append(
                {
                    "raw_id": raw_id,
                    "status": "written",
                    "路": 项.get("路"),
                    "改动数": len(改动),
                    "样例": [
                        f"{f.get('from')}→{f.get('to')}"
                        for f in 改动[:5]
                    ],
                }
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("回写 raw_id=%s 失败: %s", raw_id, exc)
            统计["失败数"] += 1
            统计["明细"].append({"raw_id": raw_id, "status": "error", "error": str(exc)[:120]})

    return 统计


async def 行是否已纠过(db: AsyncSession, raw_id: int) -> bool:
    """查单行是否已有纠错留痕(幂等预检)。"""
    r = await db.execute(
        sa_text("SELECT metadata_json FROM kb_raw_data WHERE id=:id"),
        {"id": int(raw_id)},
    )
    row = r.first()
    if not row:
        return False
    return _已纠过(_解析meta(row[0]))
