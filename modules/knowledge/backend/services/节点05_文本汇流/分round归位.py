# -*- coding: utf-8 -*-
"""按 page/round 把 kb_raw_data 行组装成三路文本。

round: 1=text, 2=ocr, 3=vision
不依赖节点③子文件，逻辑对齐其组页字典策略。
"""
from __future__ import annotations

from typing import Any


def _meta_dict(meta: Any) -> dict[str, Any] | None:
    if isinstance(meta, dict):
        return meta
    return None


def _vision_desc(content: str, meta: dict[str, Any] | None) -> tuple[str, str]:
    """返回 (vision_desc, source_tag)。"""
    if meta:
        for key in ("description", "vision_desc", "desc"):
            val = meta.get(key)
            if isinstance(val, str) and val.strip():
                return val, f"metadata.{key}"
        role = str(meta.get("role") or "").lower()
        if role in {"vision_describe", "describe", "description"} and content.strip():
            return content, "round3_role_describe"
    return content or "", "round3_content"


def _better_content(old: str, new: str, old_status: str | None, new_status: str | None) -> bool:
    """同 round 多行择优：done 优先，再最长。"""
    old_s = (old_status or "").lower()
    new_s = (new_status or "").lower()
    if new_s == "done" and old_s != "done":
        return True
    if old_s == "done" and new_s != "done":
        return False
    return len(new or "") >= len(old or "")


def 空页槽(page: int) -> dict[str, Any]:
    return {
        "page": page,
        "text": "",
        "ocr": "",
        "vision": "",
        "vision_desc": "",
        "vision_desc_source": "round3_content",
        "text_id": None,
        "ocr_id": None,
        "vision_id": None,
        "text_status": None,
        "ocr_status": None,
        "vision_status": None,
        "text_meta": None,
        "ocr_meta": None,
        "vision_meta": None,
        "evidence_ids": [],
        "round_texts": {},
    }


def 组页字典(行列表: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    """把 raw 行按 page 聚成三路槽位。"""
    页表: dict[int, dict[str, Any]] = {}
    for 行 in 行列表:
        page = int(行["page"])
        槽 = 页表.setdefault(page, 空页槽(page))
        st = (行.get("source_type") or "").lower()
        rnd = int(行.get("round") or 0)
        content = 行.get("content") or ""
        rid = int(行["id"])
        status = 行.get("status")
        meta = _meta_dict(行.get("metadata_json"))
        槽["evidence_ids"].append(rid)

        if rnd == 1 or st == "text":
            if _better_content(槽["text"], content, 槽.get("text_status"), status) or not 槽["text"]:
                槽["text"] = content
                槽["text_id"] = rid
                槽["text_meta"] = meta
                槽["text_status"] = status
                槽["round_texts"][1] = content
        elif rnd == 2 or st == "ocr":
            if _better_content(槽["ocr"], content, 槽.get("ocr_status"), status) or not 槽["ocr"]:
                槽["ocr"] = content
                槽["ocr_id"] = rid
                槽["ocr_meta"] = meta
                槽["ocr_status"] = status
                槽["round_texts"][2] = content
        elif rnd == 3 or st == "vision":
            if _better_content(槽["vision"], content, 槽.get("vision_status"), status) or not 槽["vision"]:
                槽["vision"] = content
                槽["vision_id"] = rid
                槽["vision_meta"] = meta
                槽["vision_status"] = status
                槽["round_texts"][3] = content
                desc, src = _vision_desc(content, meta)
                槽["vision_desc"] = desc
                槽["vision_desc_source"] = src
    return 页表


def 页状态(槽: dict[str, Any]) -> str:
    has = any(bool((槽.get(k) or "").strip()) for k in ("text", "ocr", "vision"))
    if not has:
        return "empty"
    filled = sum(1 for k in ("text", "ocr", "vision") if (槽.get(k) or "").strip())
    return "ok" if filled == 3 else "partial"
