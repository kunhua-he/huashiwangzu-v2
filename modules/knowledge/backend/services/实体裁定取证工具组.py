"""实体裁定取证工具组(护栏8专用,零行业硬编码)。

给"两个都像真词"的灰区裁定(原词是不是候选词的OCR错写)提供证据。判据不写死在提示词里,
而是让模型看真实证据自己判。换行业只换数据库内容,本工具组一字不改。

三个工具,每个查询控制在1-2秒内(全走 trgm 索引 / 纯计算):
  查词频(词)          → 该词在干净文本层(base_parse非图片)出现在几篇文档(权威度铁证)
  查上下文(词)        → 捞该词的真实原文片段(它到底怎么用),限量限长保证秒回
  差异字定位(原,候选)  → 纯代码逐字位对比,列出第几字、原字→候选字(形近/音近判据)

第一性原理(华哥):文本层100%正确。候选词高频=它就是对的;原词查无=它是变体误写。
证据齐了,判该不该并就退化成小学生都能做的题——不需要模型懂这个行业。
"""
from __future__ import annotations

import logging
from sqlalchemy import text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# 图片扩展名(排除图片层的OCR/VLM噪音,只认干净文本层)
_IMG_EXT = [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff", ".svg"]
_IMG_EXT_SQL = "(" + ",".join(f"'{e}'" for e in _IMG_EXT) + ")"


async def 查词频(db: AsyncSession, owner_id: int, 词: str) -> int:
    """该词在干净文本层出现在多少篇文档里。走 trgm 索引,3字以上~2ms,是"权威度"的铁证。

    篇数高=该词是库里真实存在的权威写法;篇数0=库里根本没这个词(可能是变体误写)。
    """
    if not 词:
        return 0
    r = await db.execute(
        sa_text(
            f"""SELECT count(DISTINCT c.document_id)
                FROM kb_chunks c JOIN kb_documents d ON d.id = c.document_id
                WHERE c.owner_id = :o AND c.index_layer = 'base_parse'
                  AND d.extension NOT IN {_IMG_EXT_SQL}
                  AND c.text LIKE :w"""
        ),
        {"o": owner_id, "w": f"%{词}%"},
    )
    return int(r.first()[0])


def 差异字定位(原词: str, 候选词: str) -> list[dict]:
    """纯计算:逐字位对比原词和候选词,列出不同的字位。等长才逐位比,不等长返回整体差异。

    返回 [{"位":i, "原字":x, "候选字":y}]。形近/音近的字对是"该并"信号,词义不同是"该留"信号。
    """
    if 原词 == 候选词:
        return []
    if len(原词) == len(候选词):
        return [
            {"位": i, "原字": a, "候选字": b}
            for i, (a, b) in enumerate(zip(原词, 候选词))
            if a != b
        ]
    # 不等长:退化为整体对比(交给模型看整词)
    return [{"位": -1, "原字": 原词, "候选字": 候选词}]


async def 查上下文(db: AsyncSession, owner_id: int, 词: str, 条数: int = 5, 每条长: int = 160) -> list[str]:
    """捞该词在干净文本层的真实原文片段(它到底怎么用),让模型看语境判词义。

    走 trgm 索引 + LIMIT 提前停,亚毫秒级。每条截取命中词周围一段(前后各若干字),避免整块巨文本。
    """
    if not 词:
        return []
    r = await db.execute(
        sa_text(
            f"""SELECT c.text
                FROM kb_chunks c JOIN kb_documents d ON d.id = c.document_id
                WHERE c.owner_id = :o AND c.index_layer = 'base_parse'
                  AND d.extension NOT IN {_IMG_EXT_SQL}
                  AND c.text LIKE :w
                LIMIT :n"""
        ),
        {"o": owner_id, "w": f"%{词}%", "n": 条数},
    )
    片段: list[str] = []
    半窗 = max(20, 每条长 // 2)
    for (文本,) in r.all():
        if not 文本:
            continue
        pos = 文本.find(词)
        if pos < 0:
            片段.append(文本[:每条长])
            continue
        起 = max(0, pos - 半窗)
        止 = min(len(文本), pos + len(词) + 半窗)
        seg = ("…" if 起 > 0 else "") + 文本[起:止].replace("\n", " ").strip() + ("…" if 止 < len(文本) else "")
        片段.append(seg)
    return 片段
