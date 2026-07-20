# -*- coding: utf-8 -*-
"""LLM补充：文本层已权威时，只从 OCR/VLM 抽「文本层没有的新信息」追加。

干什么：可选增强。失败 graceful → 返回空串，主流程只用文本层。
入参：round1/2/3 文本
出参：{"supplement": str, "llm_called": bool, ...}
依赖：gateway_router + timed_llm_chat
模型：profile_key=grok-4.5（provider=grok-local-gateway）

prompt 写死（投件信照抄）。
"""
from __future__ import annotations

import logging
import re
from typing import Any

from app.gateway.router import gateway_router

from ..llm_diagnostics import timed_llm_chat

logger = logging.getLogger("v2.knowledge.node06.supplement")

# 投件信：grok-local-gateway / grok-4.5；gateway 侧 profile 名为 grok-4.5
模型档案 = "grok-4.5"

系统提示 = (
    "你是文档融合助手。权威文本已100%正确，你只能补充其中没有的新信息。"
    "不要改写、不要复述权威文本。没有新信息就返回空。"
)


def _构建用户提示(round1: str, round2: str, round3: str) -> str:
    # 投件信写死的 prompt 模板
    return (
        "以下是文档某页的权威文本(来自直接文本提取,100%正确)。\n"
        "请从OCR和视觉描述里找出文本层里没有的新信息(如:图片里的数字/"
        "表格/额外说明),用1-3句追加到文本后。\n"
        "若OCR/视觉描述和文本层内容高度重合(80%以上),直接返回空字符串。\n"
        f"权威文本:{round1[:3000]}\n"
        f"OCR补充:{round2[:1000]}\n"
        f"视觉补充:{round3[:1000]}"
    )


def _清洗补充(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        return ""
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    # 模型有时返回 JSON / 「无」/ empty
    low = text.lower()
    if low in {"", "空", "无", "none", "null", "n/a", '""', "''", "{}"}:
        return ""
    if re.fullmatch(r'\{?\s*"?supplement"?\s*:\s*""\s*\}?', text, re.I):
        return ""
    # 过长视为复述，丢弃（补充应 1-3 句）
    if len(text) > 800:
        text = text[:800].rstrip()
    return text


async def 补充新信息(
    round1: str,
    round2: str,
    round3: str,
    *,
    document_id: int | None = None,
    page: int | None = None,
) -> dict[str, Any]:
    """从 OCR/VLM 抽新信息。失败返回空补充，不抛。"""
    r1 = (round1 or "").strip()
    r2 = (round2 or "").strip()
    r3 = (round3 or "").strip()
    # 没有可补充源 → 不烧 LLM
    if not r2 and not r3:
        return {
            "supplement": "",
            "llm_called": False,
            "skipped": True,
            "reason": "no_ocr_vision",
        }
    # OCR/VLM 都很短 → 跳过
    if len(r2) + len(r3) < 30:
        return {
            "supplement": "",
            "llm_called": False,
            "skipped": True,
            "reason": "ocr_vision_too_short",
        }

    try:
        result = await timed_llm_chat(
            logger=logger,
            stage="fusion",
            profile_key=模型档案,
            messages=[
                {"role": "system", "content": 系统提示},
                {"role": "user", "content": _构建用户提示(r1, r2, r3)},
            ],
            chat_func=gateway_router.chat,
            document_id=document_id,
            page=page,
            extra={"mode": "text_supplement"},
        )
        supplement = _清洗补充(result.get("content") or "")
        return {
            "supplement": supplement,
            "llm_called": True,
            "skipped": False,
            "model_degraded": bool(result.get("model_degraded")),
            "model_diagnostics": result.get("model_diagnostics") or {},
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("LLM补充失败(graceful，只用文本层): %s", exc)
        return {
            "supplement": "",
            "llm_called": True,
            "skipped": False,
            "error": str(exc)[:200],
            "graceful": True,
        }


def 追加到文本(权威文本: str, 补充: str) -> str:
    """把补充接到权威文本后；补充空则原样。"""
    base = (权威文本 or "").rstrip()
    extra = (补充 or "").strip()
    if not extra:
        return base
    if extra in base:
        return base
    return f"{base}\n\n【补充】{extra}"
