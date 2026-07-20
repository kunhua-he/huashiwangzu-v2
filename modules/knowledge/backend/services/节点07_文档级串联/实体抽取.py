# -*- coding: utf-8 -*-
"""实体抽取：文档级一次出 name+type_name+confidence+关系。

干什么：把该文档全部融合页拼成整篇正文，一次调 LLM，解析 JSON。
入参：db/document_id/owner_id；出参：{"entities":[...], "relationships":[...], ...}
依赖：gateway_router / timed_llm_chat / load_prompt_detached(TENTITY)
提示词走 framework_prompt_templates id=2。
留痕：输入组装 / 模型返回 / 解析结果 写入 kb_analysis_artifacts。
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from time import perf_counter
from typing import Any

from app.gateway.router import gateway_router
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..analysis_artifact_service import record_analysis_artifact, stable_hash
from ..llm_diagnostics import timed_llm_chat
from ..model_routing import resolve_knowledge_profile
from ..prompt_utils import TENTITY, load_prompt_detached

logger = logging.getLogger("v2.knowledge.node07.extract")

最短文本 = 20
页分隔线 = "——————————"

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


def 组装文档正文(fusions: list[Any]) -> tuple[str, list[dict[str, Any]]]:
    """把多页 fused_text 拼成整篇正文，页间用分隔线。"""
    parts: list[str] = []
    page_meta: list[dict[str, Any]] = []
    for pf in fusions:
        page = int(getattr(pf, "page", 0) or 0)
        text = (getattr(pf, "fused_text", None) or "").strip()
        if len(text) < 最短文本:
            page_meta.append({"page": page, "chars": len(text), "skipped": True})
            continue
        page_meta.append({"page": page, "chars": len(text), "skipped": False})
        parts.append(f"第{page}页\n{text}")
    body = f"\n{页分隔线}\n".join(parts)
    return body, page_meta


async def _留痕(
    *,
    owner_id: int,
    document_id: int,
    unit_key: str,
    status: str,
    reason: str = "",
    input_payload: dict | None = None,
    output_payload: dict | None = None,
    model_profile: str | None = None,
    model_used: str | None = None,
    diagnostics: dict | None = None,
    metrics: dict | None = None,
    duration_ms: int | None = None,
    started_at: datetime | None = None,
) -> int | None:
    """每步操作立刻落 kb_analysis_artifacts，失败不拖垮主流程。"""
    try:
        return await record_analysis_artifact(
            owner_id=owner_id,
            document_id=document_id,
            file_id=None,
            stage="graph",
            status=status,
            unit_type="document_step",
            unit_key=unit_key,
            input_hash=stable_hash(input_payload or {}),
            output_hash=stable_hash(output_payload or {}),
            model_profile=model_profile,
            model_used=model_used,
            reason=reason,
            diagnostics=diagnostics or {},
            metrics=metrics or {},
            duration_ms=duration_ms,
            started_at=started_at,
            completed_at=datetime.now(timezone.utc),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("实体抽取留痕失败 doc=%s step=%s: %s", document_id, unit_key, exc)
        return None


async def 抽取单段文本(text: str, profile_key: str | None = None) -> dict:
    """兼容入口：对任意一段正文做实体/关系抽取（文档级也会复用）。"""
    if not (text or "").strip():
        return {"entities": [], "relationships": []}

    resolved = resolve_knowledge_profile("entity", profile_key)
    system_prompt = await load_prompt_detached(TENTITY)
    try:
        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    "请从以下整篇文档（已按页分隔）中抽取实体和关系。"
                    "请综合全文抽取主体，同一主体不要因出现在多页而重复输出。\n\n"
                    f"{text}"
                ),
            },
        ]
        resp = await timed_llm_chat(
            logger=logger,
            stage="entity",
            profile_key=resolved,
            messages=messages,
            chat_func=gateway_router.chat,
            extra={"text_chars": len(text), "mode": "document"},
        )
        content = resp.get("content", "") or ""
        parsed = _抽json(content)
        return {
            "entities": 规范实体列表(parsed.get("entities", [])),
            "relationships": 规范关系列表(parsed.get("relationships", [])),
            "model_degraded": bool(resp.get("model_degraded")),
            "model_diagnostics": resp.get("model_diagnostics") or {},
            "model_used": resp.get("model_used") or resp.get("selected_profile"),
            "raw_content": content,
            "usage": resp.get("usage") or {},
            "profile_key": resolved,
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("实体抽取失败: %s", exc)
        return {"entities": [], "relationships": [], "errors": [str(exc)]}


async def 抽取文档融合页(
    db: AsyncSession,
    document_id: int,
    owner_id: int,
) -> dict[str, Any]:
    """文档级一次抽取：全部融合页拼成整篇，只打 1 次 LLM。

    返回：
    {
      entities, relationships, processed_pages, page_meta,
      mode=document_once, artifacts, errors, model_degraded, ...
    }
    """
    from ...models import KbPageFusion

    started = datetime.now(timezone.utc)
    t0 = perf_counter()
    stats: dict[str, Any] = {
        "entities": [],
        "relationships": [],
        "processed_pages": 0,
        "page_durations_ms": {},
        "page_meta": [],
        "errors": [],
        "model_degraded": False,
        "page_model_used": {},
        "page_model_diagnostics": {},
        "mode": "document_once",
        "artifacts": {},
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
        await _留痕(
            owner_id=owner_id,
            document_id=document_id,
            unit_key="entity_input",
            status="failed",
            reason="no_fused_pages",
            metrics={"processed_pages": 0},
            started_at=started,
            duration_ms=round((perf_counter() - t0) * 1000),
        )
        return stats

    body, page_meta = 组装文档正文(fusions)
    stats["page_meta"] = page_meta
    stats["processed_pages"] = sum(1 for p in page_meta if not p.get("skipped"))
    stats["input_chars"] = len(body)
    stats["total_pages"] = len(page_meta)

    # 步骤1：输入组装立刻留痕
    art_input = await _留痕(
        owner_id=owner_id,
        document_id=document_id,
        unit_key="entity_input",
        status="done",
        reason="document_concat",
        input_payload={"document_id": document_id, "page_meta": page_meta},
        output_payload={"input_chars": len(body), "preview": body[:500]},
        metrics={
            "processed_pages": stats["processed_pages"],
            "total_pages": stats["total_pages"],
            "input_chars": len(body),
            "mode": "document_once",
        },
        started_at=started,
        duration_ms=round((perf_counter() - t0) * 1000),
    )
    stats["artifacts"]["entity_input"] = art_input

    if not body.strip():
        stats["errors"].append("All fused pages skipped as too short")
        await _留痕(
            owner_id=owner_id,
            document_id=document_id,
            unit_key="entity_llm",
            status="failed",
            reason="empty_document_body",
            metrics={"input_chars": 0},
            started_at=started,
            duration_ms=round((perf_counter() - t0) * 1000),
        )
        return stats

    # 步骤2：整篇一次 LLM
    llm_started = datetime.now(timezone.utc)
    llm_t0 = perf_counter()
    result = await 抽取单段文本(body)
    llm_ms = round((perf_counter() - llm_t0) * 1000)
    stats["page_durations_ms"]["document"] = llm_ms
    stats["llm_duration_ms"] = llm_ms

    raw_content = result.get("raw_content") or ""
    llm_status = "failed" if result.get("errors") else "done"
    art_llm = await _留痕(
        owner_id=owner_id,
        document_id=document_id,
        unit_key="entity_llm",
        status=llm_status,
        reason="document_once_llm",
        input_payload={"input_chars": len(body), "mode": "document_once"},
        output_payload={
            "output_chars": len(raw_content),
            "preview": raw_content[:800],
            "usage": result.get("usage") or {},
        },
        model_profile=result.get("profile_key"),
        model_used=result.get("model_used"),
        diagnostics=result.get("model_diagnostics") or {},
        metrics={
            "input_chars": len(body),
            "output_chars": len(raw_content),
            "duration_ms": llm_ms,
            "errors": result.get("errors") or [],
        },
        started_at=llm_started,
        duration_ms=llm_ms,
    )
    stats["artifacts"]["entity_llm"] = art_llm

    entities = result.get("entities") or []
    relationships = result.get("relationships") or []
    stats["entities"] = entities
    stats["relationships"] = relationships
    stats["errors"].extend(result.get("errors") or [])
    stats["model_degraded"] = bool(result.get("model_degraded"))
    stats["page_model_used"]["document"] = result.get("model_used")
    stats["page_model_diagnostics"]["document"] = result.get("model_diagnostics")
    stats["model_used"] = result.get("model_used")

    # 步骤3：解析结果立刻留痕（即使后续落库失败也不丢）
    art_parsed = await _留痕(
        owner_id=owner_id,
        document_id=document_id,
        unit_key="entity_parsed",
        status="done" if entities or relationships else ("failed" if stats["errors"] else "done"),
        reason="parsed_entities",
        input_payload={"artifact_llm": art_llm},
        output_payload={
            "entities_count": len(entities),
            "relationships_count": len(relationships),
            "entities_sample": entities[:12],
            "relationships_sample": relationships[:12],
        },
        model_profile=result.get("profile_key"),
        model_used=result.get("model_used"),
        metrics={
            "entities_count": len(entities),
            "relationships_count": len(relationships),
            "processed_pages": stats["processed_pages"],
            "llm_duration_ms": llm_ms,
        },
        started_at=llm_started,
        duration_ms=round((perf_counter() - t0) * 1000),
    )
    stats["artifacts"]["entity_parsed"] = art_parsed
    stats["duration_ms"] = round((perf_counter() - t0) * 1000)
    return stats
