# -*- coding: utf-8 -*-
"""文本层优先：有权威 round1 时直接作 fused_text，不让 LLM 改写。

干什么：
- 判定 is_text_dominant
- 产出 fused_text = round1 原文，confidence=0.95

入参：round_texts dict[int,str], is_image bool
出参：None(非文本主导) 或 {fused_text, confidence, strategy, ...}
依赖：无外部服务，纯规则。
"""
from __future__ import annotations

from typing import Any

# 与投件信写死一致
文本层最少长度 = 50
文本层置信度 = 0.95

# 图片/伪文本：round1 常是像素分析标题，不能当尺子
伪文本前缀 = (
    "本地图片分析",
    "图像技术",
    "像素",
    "主色",
    "素材类型：未加工",
)


def 是否伪文本(content: str) -> bool:
    t = (content or "").strip()
    if not t:
        return True
    for p in 伪文本前缀:
        if t.startswith(p) or p in t[:40]:
            return True
    return False


def 判定文本主导(
    round_texts: dict[int, str],
    *,
    is_image: bool = False,
) -> bool:
    """有可用文本层 → True。图片文档永远 False。"""
    if is_image:
        return False
    text = (round_texts.get(1) or "").strip()
    if len(text) < 文本层最少长度:
        return False
    if 是否伪文本(text):
        return False
    return True


def 文本层优先融合(
    round_texts: dict[int, str],
    *,
    is_image: bool = False,
) -> dict[str, Any] | None:
    """有文本层则返回融合结果；否则 None 交给兜底。"""
    if not 判定文本主导(round_texts, is_image=is_image):
        return None
    text = (round_texts.get(1) or "").strip()
    return {
        "fused_text": text,
        "page_summary": text[:120],
        "page_title": None,
        "entities": [],
        "attributes": {"融合策略": "文本层优先"},
        "tags": [],
        "conflicts": [],
        "confidence": 文本层置信度,
        "strategy": "text_dominant",
        "is_text_dominant": True,
        "_diagnostic_fallback": False,
        "llm_called": False,
    }
