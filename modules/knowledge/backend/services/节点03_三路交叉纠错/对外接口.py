# -*- coding: utf-8 -*-
"""节点③ 唯一对外接口。

函数：纠错回写(db, document_id, owner_id) -> dict
返回：{纠正数, 回写数, 留言数, 页数, 跳过页数, 失败页数, 幂等跳过, 分支统计, 明细}

其他模块 / graph 阶段只能 import 本文件(或包级 纠错回写)，不许 import 子文件。

流程：
1. 拉该文档全部 kb_raw_data 行
2. 按页组三路 → 分支判定 → 对齐纠错
3. 回写 content + metadata 留痕
4. 灰区可选裁定(默认零 LLM，只统计)
5. 幂等：整页相关行若都已有纠错留痕且无新改动 → 跳过

失败不拖垮：单页异常只记该页错误。
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession

from .三路对齐 import 对齐一页, 组页字典
from .回写原文 import _已纠过, _解析meta, 回写纠正项
from .裁定灰区 import 处理灰区

logger = logging.getLogger("v2.knowledge.node03")


async def 纠错回写(
    db: AsyncSession,
    document_id: int,
    owner_id: int,
    *,
    启用模型裁定: bool = False,
    提交: bool = True,
) -> dict[str, Any]:
    """文档级三路交叉纠错 + 回写原文。幂等、失败不拖垮。"""
    统计: dict[str, Any] = {
        "document_id": int(document_id),
        "owner_id": int(owner_id),
        "纠正数": 0,
        "回写数": 0,
        "留言数": 0,
        "页数": 0,
        "跳过页数": 0,
        "失败页数": 0,
        "幂等跳过": 0,
        "分支统计": {"三路互校": 0, "OCR_VLM互校": 0, "跳过": 0},
        "明细": [],
        "status": "ok",
    }

    try:
        r = await db.execute(
            sa_text(
                """SELECT id, page, round, source_type, content, metadata_json, status
                   FROM kb_raw_data
                   WHERE document_id=:d AND owner_id=:o
                   ORDER BY page, round, id"""
            ),
            {"d": int(document_id), "o": int(owner_id)},
        )
        行列表 = [dict(row) for row in r.mappings().all()]
    except Exception as exc:  # noqa: BLE001
        logger.warning("文档 %s 拉 raw_data 失败: %s", document_id, exc)
        统计["status"] = "error"
        统计["error"] = str(exc)[:200]
        return 统计

    if not 行列表:
        统计["status"] = "empty"
        return 统计

    # 整文档幂等快路径：
    # 1) 所有 ocr/vision 行都已有纠错留痕 → already_done
    # 2) 或：存在目标行，且没有任何「未纠过且有实质内容」的目标行需再处理
    目标行 = [
        row
        for row in 行列表
        if int(row.get("round") or 0) in (2, 3)
        or (row.get("source_type") or "").lower() in ("ocr", "vision")
    ]
    if 目标行:
        已纠行 = [row for row in 目标行 if _已纠过(_解析meta(row.get("metadata_json")))]
        if len(已纠行) == len(目标行):
            统计["幂等跳过"] = len(目标行)
            统计["status"] = "already_done"
            return 统计
        # 部分已纠：后续页级/行级会跳过已纠行；此处不整单 return

    页表 = 组页字典(行列表)
    统计["页数"] = len(页表)
    全部纠正: list[dict] = []
    全部灰区: list[dict] = []

    for page, 页数据 in sorted(页表.items()):
        try:
            # 页级幂等：该页 ocr/vision 均已纠过则跳过
            页meta对 = []
            if 页数据.get("ocr_id"):
                页meta对.append(页数据.get("ocr_meta"))
            if 页数据.get("vision_id"):
                页meta对.append(页数据.get("vision_meta"))
            if 页meta对 and all(_已纠过(_解析meta(m)) for m in 页meta对):
                统计["幂等跳过"] += 1
                统计["跳过页数"] += 1
                continue

            对齐 = 对齐一页(页数据)
            分支 = 对齐.get("分支") or "跳过"
            统计["分支统计"][分支] = 统计["分支统计"].get(分支, 0) + 1

            if 分支 == "跳过":
                统计["跳过页数"] += 1
                continue

            纠正项 = 对齐.get("纠正项") or []
            灰区 = 对齐.get("灰区") or []
            for 项 in 纠正项:
                项["分支"] = 分支
                项["page"] = page
            全部纠正.extend(纠正项)
            全部灰区.extend(灰区)

            页纠正字数 = sum(len(x.get("改动") or []) for x in 纠正项)
            统计["纠正数"] += 页纠正字数
            统计["明细"].append(
                {
                    "page": page,
                    "分支": 分支,
                    "纠正字数": 页纠正字数,
                    "改动样例": [
                        f"{f.get('from')}→{f.get('to')}"
                        for 项 in 纠正项
                        for f in (项.get("改动") or [])[:3]
                    ][:8],
                    "灰区数": len(灰区),
                }
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("文档 %s 页 %s 纠错失败: %s", document_id, page, exc)
            统计["失败页数"] += 1
            统计["明细"].append({"page": page, "status": "error", "error": str(exc)[:120]})

    if 全部纠正:
        try:
            # 按分支分组回写(留痕里带分支)
            按分支: dict[str, list] = {}
            for 项 in 全部纠正:
                按分支.setdefault(项.get("分支") or "", []).append(项)
            回写合计 = 0
            for 分支名, 项们 in 按分支.items():
                wb = await 回写纠正项(
                    db, 项们, 分支=分支名, document_id=int(document_id)
                )
                回写合计 += int(wb.get("回写数") or 0)
            统计["回写数"] = 回写合计
            if 提交 and 回写合计:
                await db.commit()
        except Exception as exc:  # noqa: BLE001
            logger.warning("文档 %s 回写失败: %s", document_id, exc)
            统计["status"] = "writeback_error"
            统计["error"] = str(exc)[:200]
            try:
                await db.rollback()
            except Exception:  # noqa: BLE001
                pass

    if 全部灰区:
        try:
            灰 = await 处理灰区(
                db,
                int(owner_id),
                全部灰区,
                启用模型裁定=启用模型裁定,
            )
            统计["留言数"] = int(灰.get("留言数") or 0)
            统计["灰区"] = {
                "总数": len(全部灰区),
                "可纠数": 灰.get("可纠数"),
                "驳回数": 灰.get("驳回数"),
                "跳过数": 灰.get("跳过数"),
            }
        except Exception as exc:  # noqa: BLE001
            logger.warning("文档 %s 灰区处理失败: %s", document_id, exc)

    logger.info(
        "节点③ 文档 %s: 纠正字=%s 回写=%s 留言=%s 页=%s 幂等跳过=%s",
        document_id,
        统计["纠正数"],
        统计["回写数"],
        统计["留言数"],
        统计["页数"],
        统计["幂等跳过"],
    )
    return 统计


# 兼容英文别名(少数英文调用点)
async def correct_and_writeback(db: AsyncSession, document_id: int, owner_id: int, **kw) -> dict:
    return await 纠错回写(db, document_id, owner_id, **kw)
