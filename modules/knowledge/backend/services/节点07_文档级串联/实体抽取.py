# -*- coding: utf-8 -*-
"""实体抽取：按新提示词一次出 name+type_name+confidence+关系。

干什么：从页融合正文调 LLM，解析 JSON，规范成内部结构。
入参：文本 str；出参：{"entities":[...], "relationships":[...], ...}
依赖：gateway_router / timed_llm_chat / load_prompt_detached(TENTITY)
复用：entity_service 的并行页抽取模式；提示词走 framework_prompt_templates id=2。
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from time import perf_counter
from typing import Any

from app.gateway.router import gateway_router
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..llm_diagnostics import timed_llm_chat
from ..model_routing import resolve_knowledge_concurrency, resolve_knowledge_profile
from ..prompt_utils import TENTITY, load_prompt_detached

logger = logging.getLogger("v2.knowledge.node07.extract")

页并发默认 = 6
最短文本 = 20
最大截断 = 6000

# 18 类白名单（与 kb_semantic_types 对齐，噪音含别名 noise）
十八类 = {
    "成分", "原料", "功效", "品类", "产品", "品牌", "系列", "规格",
    "肤质", "人物", "组织", "地点", "事件", "时间", "技术标准",
    "视觉素材", "营销内容", "噪音",
}
九谓词 = {"拥有", "属于", "包含", "相关", "引用", "参与", "位于", "产生", "领导"}


def _剥代码块(content: str) -> str:
    content = (content or "").strip()
    if content.startswith("```"):
        lines = content.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        content = "\n".join(lines)
    return content.strip()


def _抽json(content: str) -> dict:
    """尽量从模型输出里抠 JSON 对象。"""
    text = _剥代码块(content)
    if not text:
        return {}
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else {}
    except Exception:  # noqa: BLE001
        m = re.search(r"\{[\s\S]*\}", text)
        if not m:
            return {}
        try:
            obj = json.loads(m.group(0))
            return obj if isinstance(obj, dict) else {}
        except Exception:  # noqa: BLE001
            return {}


def _规范类型名(raw: str) -> str:
    name = (raw or "").strip()
    if name in ("noise", "Noise", "NOISE", "噪 音"):
        return "噪音"
    if name in 十八类:
        return name
    # 旧提示词兼容映射
    映射 = {
        "人名": "人物", "人物名": "人物", "品牌名": "品牌", "产品名": "产品",
        "机构": "组织", "组织机构": "组织", "公司": "组织", "证书": "技术标准",
        "检验标准": "技术标准", "标准": "技术标准", "其他": "噪音", "通用": "噪音",
        "成分名": "成分", "功效名": "功效",
    }
    if name in 映射:
        return 映射[name]
    return "噪音"


def _规范谓词(raw: str) -> str:
    p = (raw or "").strip()
    if p in 九谓词:
        return p
    映射 = {
        "relation": "相关", "相关于": "相关", "关联": "相关",
        "归属": "属于", "从属": "属于", "拥有者": "拥有",
        "含有": "包含", "包括": "包含", "引用了": "引用",
    }
    return 映射.get(p, "相关" if p else "相关")


def 规范实体列表(items: Any) -> list[dict]:
    """把模型返回规范成 list[dict](name/type_name/description/confidence)。"""
    out: list[dict] = []
    for it in items or []:
        if isinstance(it, str):
            name = it.strip()
            if name:
                out.append({
                    "name": name,
                    "type_name": "噪音",
                    "description": "",
                    "confidence": 0.4,
                })
            continue
        if not isinstance(it, dict):
            continue
        name = (it.get("name") or "").strip()
        if not name:
            continue
        conf_raw = it.get("confidence", 0.7)
        try:
            conf = float(conf_raw)
        except (TypeError, ValueError):
            conf = 0.7
        conf = max(0.0, min(1.0, conf))
        type_name = _规范类型名(
            str(it.get("type_name") or it.get("category") or it.get("type") or "噪音")
        )
        out.append({
            "name": name,
            "type_name": type_name,
            "description": str(it.get("description") or it.get("evidence") or "")[:500],
            "confidence": conf,
            # 兼容旧字段
            "category": type_name,
        })
    return out


def 规范关系列表(items: Any) -> list[dict]:
    out: list[dict] = []
    for it in items or []:
        if not isinstance(it, dict):
            continue
        source = (it.get("source") or "").strip()
        target = (it.get("target") or "").strip()
        if not source or not target:
            continue
        predicate = _规范谓词(
            str(it.get("predicate") or it.get("relation") or it.get("relation_type") or "相关")
        )
        out.append({
            "source": source,
            "target": target,
            "predicate": predicate,
            "relation": predicate,  # 兼容旧写边逻辑
            "evidence": str(it.get("evidence") or it.get("description") or "")[:500],
            "description": str(it.get("evidence") or it.get("description") or "")[:500],
        })
    return out


async def 抽取单段文本(text: str, profile_key: str | None = None) -> dict:
    """对一段融合正文做实体/关系抽取。"""
    if not (text or "").strip():
        return {"entities": [], "relationships": []}

    resolved = resolve_knowledge_profile("entity", profile_key)
    system_prompt = await load_prompt_detached(TENTITY)
    try:
        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"请提取以下内容的实体和关系：\n\n{text[:最大截断]}",
            },
        ]
        resp = await timed_llm_chat(
            logger=logger,
            stage="entity",
            profile_key=resolved,
            messages=messages,
            chat_func=gateway_router.chat,
            extra={"text_chars": len(text)},
        )
        content = resp.get("content", "") or ""
        parsed = _抽json(content)
        return {
            "entities": 规范实体列表(parsed.get("entities", [])),
            "relationships": 规范关系列表(parsed.get("relationships", [])),
            "model_degraded": bool(resp.get("model_degraded")),
            "model_diagnostics": resp.get("model_diagnostics") or {},
            "model_used": resp.get("model_used") or resp.get("selected_profile"),
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("实体抽取失败: %s", exc)
        return {"entities": [], "relationships": [], "errors": [str(exc)]}


async def 抽取文档融合页(
    db: AsyncSession,
    document_id: int,
    owner_id: int,
) -> dict[str, Any]:
    """从 kb_page_fusions 并行抽各页实体。

    返回：
    {
      entities: [{... , page}],
      relationships: [...],
      processed_pages, page_durations_ms, errors, model_degraded, ...
    }
    """
    from ...models import KbPageFusion

    stats: dict[str, Any] = {
        "entities": [],
        "relationships": [],
        "processed_pages": 0,
        "page_durations_ms": {},
        "errors": [],
        "model_degraded": False,
        "page_model_used": {},
        "page_model_diagnostics": {},
    }

    r = await db.execute(
        select(KbPageFusion)
        .where(
            KbPageFusion.document_id == document_id,
            KbPageFusion.owner_id == owner_id,
            KbPageFusion.fused_text != "",
        )
        .order_by(KbPageFusion.page)
    )
    fusions = r.scalars().all()
    if not fusions:
        stats["errors"].append("No fused pages found")
        return stats

    page_concurrency = resolve_knowledge_concurrency("entity_extract", 页并发默认)
    sem = asyncio.Semaphore(page_concurrency)

    async def _一页(pf) -> dict:
        text = pf.fused_text or ""
        page = int(pf.page)
        if len(text) < 最短文本:
            return {"page": page, "skipped": True}
        async with sem:
            t0 = perf_counter()
            result = await 抽取单段文本(text)
            return {
                "page": page,
                "duration_ms": round((perf_counter() - t0) * 1000),
                "result": result,
            }

    page_results = await asyncio.gather(
        *(_一页(pf) for pf in fusions),
        return_exceptions=True,
    )
    for item in page_results:
        if isinstance(item, Exception):
            stats["errors"].append(str(item))
            continue
        if item.get("skipped"):
            continue
        page = int(item["page"])
        result = item["result"]
        stats["page_durations_ms"][page] = int(item.get("duration_ms") or 0)
        ents = result.get("entities") or []
        for ent in ents:
            ent = dict(ent)
            ent["page"] = page
            stats["entities"].append(ent)
        stats["relationships"].extend(result.get("relationships") or [])
        stats["errors"].extend(result.get("errors") or [])
        stats["page_model_diagnostics"][page] = result.get("model_diagnostics")
        stats["page_model_used"][page] = result.get("model_used")
        if result.get("model_degraded"):
            stats["model_degraded"] = True
        stats["processed_pages"] += 1

    return stats
