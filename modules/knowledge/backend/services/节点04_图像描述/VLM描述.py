# -*- coding: utf-8 -*-
"""VLM描述：只做视觉内容描述（round3），不重复认字。

干什么：图片字节 → grok-4.5-vision 视觉描述。
聚焦：产品视觉/人物场景/版式结构/颜色风格/业务标签（提示词走 knowledge_raw_vision）。
入参：img_bytes, mime_type
出参：{content, status, model_used, metadata, duration_ms, ...}
依赖：describe_image_detailed
模型：强制 grok-4.5-vision
"""
from __future__ import annotations

import logging
from time import perf_counter
from typing import Any

from app.services.model_services import describe_image_detailed

from ..model_routing import knowledge_model_call_slot, record_model_rate_limit
from ..prompt_utils import TRAW_VISION, load_prompt

logger = logging.getLogger("v2.knowledge.node04.vision")

VLM档案 = "grok-4.5-vision"


async def 描述(
    img_bytes: bytes,
    mime_type: str = "image/jpeg",
    *,
    document_id: int | None = None,
    page: int | None = None,
) -> dict[str, Any]:
    """对图片做视觉描述（不重复 OCR）。失败不抛。"""
    from app.database import AsyncSessionLocal

    started = perf_counter()
    if not img_bytes:
        return {
            "content": "",
            "status": "failed",
            "error": "empty_image",
            "model_used": VLM档案,
            "llm_called": False,
            "duration_ms": 0,
            "metadata": {"method": "vlm_vision", "profile_key": VLM档案},
        }

    error_message = ""
    content = ""
    metadata: dict[str, Any] = {
        "method": "vlm_vision",
        "profile_key": VLM档案,
        "node": "04",
        "role": "vision_describe",
    }
    try:
        async with AsyncSessionLocal() as task_db:
            prompt = await load_prompt(task_db, TRAW_VISION, release_transaction=True)
        async with knowledge_model_call_slot("raw_vision"):
            result = await describe_image_detailed(
                img_bytes,
                prompt=prompt,
                mime_type=mime_type or "image/jpeg",
                profile_key=VLM档案,
            )
        content = str(result.get("content") or "").replace("\x00", "").strip()
        diag = (result.get("diagnostics") or {}) if isinstance(result, dict) else {}
        selected = str(diag.get("selected_profile") or VLM档案)
        metadata.update({
            "provider": str(diag.get("selected_provider") or "grok-local-gateway"),
            "model_used": selected,
            "model_degraded": bool(diag.get("fallback_used")) and selected != VLM档案,
            "model_diagnostics": {
                "requested_profile": VLM档案,
                "selected_profile": selected,
                "selected_provider": str(diag.get("selected_provider") or ""),
                "fallback_used": bool(diag.get("fallback_used")),
            },
        })
        if diag.get("image_preprocess"):
            metadata["image_preprocess"] = diag["image_preprocess"]
    except Exception as exc:  # noqa: BLE001
        pause = record_model_rate_limit("raw_vision", error_message=exc)
        if pause.get("paused"):
            logger.error("节点④ 描述 触发 rate-limit pause: %s", pause)
        logger.warning(
            "节点④ 描述失败 doc=%s page=%s: %s", document_id, page, exc
        )
        content = ""
        error_message = str(exc)[:300]
        metadata["error"] = error_message

    duration_ms = round((perf_counter() - started) * 1000)
    status = "done" if content else ("failed" if error_message else "degraded")
    return {
        "content": content,
        "status": status,
        "error": error_message or None,
        "model_used": str(metadata.get("model_used") or VLM档案),
        "metadata": metadata,
        "duration_ms": duration_ms,
        "llm_called": True,
        "chars": len(content),
    }
