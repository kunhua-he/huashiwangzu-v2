# -*- coding: utf-8 -*-
"""LLM兜底：无文本层（图片 / round1 空）时，OCR+VLM 喂 LLM 融合。

干什么：复用 fusion_service._llm_fuse 的 is_image 逻辑；模型改 grok-4.5。
入参：round_texts, is_image
出参：与 _llm_fuse 同结构 dict
依赖：fusion_service._llm_fuse / _fallback_fusion / timed_llm_chat
模型：profile_key=grok-4.5（provider=grok-local-gateway）
"""
from __future__ import annotations

import json
import logging
from typing import Any

from app.gateway.router import gateway_router

from ..llm_diagnostics import timed_llm_chat
from ..prompt_utils import TFUSION, load_prompt_detached

logger = logging.getLogger("v2.knowledge.node06.fallback")

模型档案 = "grok-4.5"


async def LLM兜底融合(
    round_texts: dict[int, str],
    *,
    is_image: bool = True,
    document_id: int | None = None,
    page: int | None = None,
) -> dict[str, Any]:
    """无文本层时的 LLM 融合。失败走 fusion_service 启发式兜底。"""
    # 图片：剔除 round1 像素分析（与 fusion_service._fusion_round_texts 一致）
    if is_image:
        feed = {r: t for r, t in round_texts.items() if r != 1}
    else:
        feed = dict(round_texts)

    system_prompt = await load_prompt_detached(TFUSION)
    if is_image or not (feed.get(1) or "").strip():
        user_message = f"""请交叉印证以下图片的两轮采集结果，输出融合后的权威描述。
注意:这是图片,没有文本提取层。图里的文字以 OCR 为准,画面内容以视觉描述为准。
不要把像素尺寸/分辨率/亮度等技术元数据写进 fused_text 正文。

=== 图内文字：截图 OCR ===
{feed.get(2, '(无)')[:4000]}

=== 画面内容：视觉描述 ===
{feed.get(3, '(无)')[:4000]}"""
    else:
        # 极少数：非图片但 round1 太短，仍三路喂（不应改写已有短文本时由上层决定）
        user_message = f"""请交叉印证以下三轮采集结果，输出融合后的权威描述。

=== 第1轮：文本提取 ===
{feed.get(1, '(无)')[:4000]}

=== 第2轮：截图 OCR ===
{feed.get(2, '(无)')[:4000]}

=== 第3轮：视觉构成 ===
{feed.get(3, '(无)')[:4000]}"""

    try:
        result = await timed_llm_chat(
            logger=logger,
            stage="fusion",
            profile_key=模型档案,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            chat_func=gateway_router.chat,
            document_id=document_id,
            page=page,
            extra={"mode": "llm_fallback", "is_image": is_image},
        )
        content = (result.get("content") or "").strip()
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(lines[1:]) if len(lines) > 1 else content
            if content.endswith("```"):
                content = content[:-3].strip()
        try:
            parsed = json.loads(content)
        except Exception:  # noqa: BLE001
            # 非 JSON：整段当 fused_text
            parsed = {
                "fused_text": content,
                "page_summary": content[:120],
                "confidence": 0.65,
                "conflicts": [],
            }
        if not (parsed.get("fused_text") or "").strip():
            from ..fusion_service import _fallback_fusion

            fallback = _fallback_fusion(feed, parsed.get("conflicts", []))
            fallback["strategy"] = "llm_fallback_empty"
            fallback["llm_called"] = True
            return fallback
        if not (parsed.get("page_summary") or "").strip():
            parsed["page_summary"] = str(parsed.get("fused_text") or "")[:120]
        parsed["_diagnostic_fallback"] = False
        parsed["model_degraded"] = bool(result.get("model_degraded"))
        parsed["model_diagnostics"] = result.get("model_diagnostics") or {}
        parsed["strategy"] = "llm_fallback"
        parsed["llm_called"] = True
        parsed["is_text_dominant"] = False
        attrs = dict(parsed.get("attributes") or {})
        attrs["融合策略"] = "LLM兜底"
        parsed["attributes"] = attrs
        return parsed
    except Exception as exc:  # noqa: BLE001
        logger.warning("LLM兜底失败，启发式 fallback: %s", exc)
        from ..fusion_service import _fallback_fusion

        fb = _fallback_fusion(feed)
        fb["strategy"] = "heuristic_fallback"
        fb["llm_called"] = True
        fb["error"] = str(exc)[:200]
        fb["is_text_dominant"] = False
        return fb
