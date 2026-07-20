# -*- coding: utf-8 -*-
"""页面渲染：从页面资产取图字节。

干什么：包装 page_asset_service.load_page_asset_bytes。
入参：db, document_id, page（可选 owner_id 仅日志）
出参：{img_bytes, mime_type, diagnostics} 或 None
依赖：page_asset_service（page_render 阶段已沉淀资产）
说明：投件信写的 get_page_asset_bytes 在代码里实际名是 load_page_asset_bytes。
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("v2.knowledge.node04.render")


async def 获取页面图片(
    db: AsyncSession,
    document_id: int,
    page: int,
    owner_id: int | None = None,
) -> dict[str, Any] | None:
    """读取已 materialize 的页面图片字节。无资产返回 None。"""
    from ..page_asset_service import load_page_asset_bytes

    loaded = await load_page_asset_bytes(db, document_id=int(document_id), page=int(page))
    if loaded is None:
        logger.warning(
            "文档%s 页%s 无页面资产(owner=%s)，需先跑 page_render",
            document_id,
            page,
            owner_id,
        )
        return None
    img_bytes, mime_type, diagnostics = loaded
    return {
        "img_bytes": img_bytes,
        "mime_type": mime_type or "image/jpeg",
        "diagnostics": diagnostics or {},
        "byte_size": len(img_bytes or b""),
    }
