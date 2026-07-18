# -*- coding: utf-8 -*-
"""分支判定：决定这一页走哪条校验路。

入参：一页三路 content 字典 {text, ocr, vision}
出参：分支名 '三路互校' | 'OCR_VLM互校' | '跳过'

规则：
- 有可用文本层(round1 content 非空且不是“本地图片分析”伪文本) → 三路互校
- 无文本层但 OCR/VLM 至少一路有字 → OCR↔VLM 互校
- 都空 → 跳过
"""
from __future__ import annotations

_伪文本前缀 = ("本地图片分析", "hello")


def 是否可用文本层(content: str | None) -> bool:
    """文本层是否能当尺子。伪文本/过短不算。"""
    文 = (content or "").strip()
    if len(文) < 8:
        return False
    for 前 in _伪文本前缀:
        if 文.startswith(前):
            return False
    # 必须含汉字，纯英文/数字不能当中文尺子
    return any("一" <= ch <= "鿿" for ch in 文)


def 是否有实质内容(content: str | None) -> bool:
    文 = (content or "").strip()
    return len(文) >= 4


def 判定分支(页数据: dict) -> str:
    """判定单页分支。

    页数据期望键: text / ocr / vision (均可缺省)。
    """
    文本 = 页数据.get("text") or ""
    ocr = 页数据.get("ocr") or ""
    vision = 页数据.get("vision") or ""

    if 是否可用文本层(文本):
        # 至少有一路脏数据才值得纠；否则跳过
        if 是否有实质内容(ocr) or 是否有实质内容(vision):
            return "三路互校"
        return "跳过"

    if 是否有实质内容(ocr) or 是否有实质内容(vision):
        return "OCR_VLM互校"
    return "跳过"
