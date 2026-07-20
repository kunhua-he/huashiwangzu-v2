# -*- coding: utf-8 -*-
"""主体枚举库存落盘：词/出现/组合/试卷题。

原则：
- 每个词组都必须有 semantic_role（语义角色）
- graph_include 只控制是否进主图谱/主召回
- 不是“噪音=扔掉”
- 热路径禁止逐词 SELECT；先内存累计，最后批量 UPSERT
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ._动态加载 import 取属性

归一化 = 取属性("分词", "归一化")

# 通用结构角色（不是业务主体白名单）
_MEASURE = {
    "mg", "kg", "g", "ml", "l", "μg", "ug", "ppm", "ppb", "%", "％",
    "单位", "限值", "浓度", "含量", "结果", "方法", "检出",
}
_TEMPLATE = {
    "检验", "检测", "报告", "样品", "送检", "受理", "编号", "专用章",
    "第四章", "第一法", "第二法", "页", "共", "本页以下空白",
}
_FUNCTION = {
    "的", "了", "和", "与", "及", "或", "在", "是", "为", "对", "等",
    "通过", "进行", "可以", "以及", "其中", "其他", "各种", "相关",
}
_MODIFIER_HINT = {
    "正确的", "良好的", "专业的", "标准的", "完整的", "最新", "仅供",
}
_LATIN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_.\-]*")
_FIELD_GLUE_HINTS = {
    "商品名", "收货人", "收货电话", "下单人", "分享人", "归属人", "手机号",
    "门店信息", "活动状态", "活动名称", "活动折扣", "零售价", "活动价", "抵扣金额",
    "实付金额", "规格属性", "完成时间", "引流工具", "岗位id", "门店id",
}
_SENTENCE_GLUE_RE = re.compile(
    r"(页面为|图片为|页脚|文字包括|字段|表格字段|记录\d+|活动状态|门店信息|"
    r"可见文字|可见产品|底部口号|正面可见|出具的|包含|展示|标注|注明|说明文字|"
    r"整体呈现|可关联标签|疑似|类似|主题包括|背景为|画面未见|现场可见|投影内容|"
    r"价格或功效|右侧|前景可见|在本次|本次|优秀门店|线下门店)"
)
_LATIN_STOP = {
    "a", "an", "and", "or", "the", "to", "of", "in", "on", "for", "with", "by", "from",
    "at", "as", "is", "are", "be", "this", "that", "these", "those", "no", "not",
    "before", "after", "case", "show", "logo", "skin", "beauty", "cream", "product",
    "whitening", "moisturizing", "rejuvenating", "replenishing", "revitalizing", "concentrated",
    "breakthrough", "pain", "freckle", "days", "yellow", "reach", "defects", "within", "ecological",
}


def _field_glue_count(token: str) -> int:
    raw = str(token or "")
    norm = 归一化(raw)
    return sum(1 for h in _FIELD_GLUE_HINTS if h in raw or 归一化(h) in norm)


def _looks_sentence_glue(token: str) -> bool:
    raw = str(token or "").strip()
    norm = 归一化(raw)
    if len(norm) < 12:
        return False
    if _looks_latin_phrase(raw):
        return False
    if _field_glue_count(raw) >= 2:
        return True
    if _SENTENCE_GLUE_RE.search(raw):
        return True
    return len(norm) >= 24


def _looks_latin_phrase(token: str) -> bool:
    raw = str(token or "").strip()
    norm = 归一化(raw)
    if not norm:
        return False
    if _LATIN_RE.fullmatch(raw or ""):
        return True
    return bool(re.fullmatch(r"[a-z][a-z0-9]{11,}", norm or ""))



def _hash(*parts: object) -> str:
    raw = "|".join(str(p or "") for p in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def 推断语义角色(
    token: str,
    *,
    candidate_types: list[str] | None = None,
) -> tuple[str, bool, float]:
    """返回 (semantic_role, graph_include, confidence)。"""
    types = [str(x).strip() for x in (candidate_types or []) if str(x).strip()]
    n = 归一化(token)
    surface = (token or "").strip()

    if _looks_sentence_glue(surface):
        return "表格页面说明", False, 0.55

    business = [t for t in types if t not in {"噪音", "通用", "term", "", "营销内容", "视觉素材"}]
    if business:
        role = f"业务类型:{business[0]}"
        return role, True, 0.85 if len(business) == 1 else 0.75

    if _looks_latin_phrase(surface):
        low = n.lower()
        if low in _LATIN_STOP:
            return "外文说明", False, 0.45
        if len(low) <= 3:
            return "外文缩写", False, 0.6
        return "外文说明", False, 0.5

    if "噪音" in types and not business:
        if n in _FUNCTION:
            return "功能连接", False, 0.8
        if n in _TEMPLATE or "培训" in surface or "仅供" in surface:
            return "模板套话", False, 0.75
        return "弱业务描述", False, 0.55

    if n in _FUNCTION:
        return "功能连接", False, 0.9
    if n in _MEASURE or re.fullmatch(r"\d+(\.\d+)?", n or ""):
        return "计量数值", False, 0.85
    if n in _TEMPLATE:
        return "模板套话", False, 0.8
    if n in _MODIFIER_HINT or (surface.endswith("的") and len(surface) <= 4):
        return "修饰限定", False, 0.7
    if n.endswith("有限公司") or n.endswith("股份有限公司"):
        return "业务类型:组织", True, 0.9
    if re.fullmatch(r"\d{4}-\d{1,2}-\d{1,2}", n or "") or re.fullmatch(r"\d{4}年\d{1,2}月\d{1,2}日", n or ""):
        return "业务类型:时间", True, 0.9
    if _LATIN_RE.fullmatch(surface or ""):
        low = n.lower()
        if low in _LATIN_STOP:
            return "外文说明", False, 0.45
        if len(low) <= 3:
            return "外文缩写", False, 0.6
        return "外文说明", False, 0.5
    if len(n) >= 4:
        return "待定主体", True, 0.45
    if len(n) == 2:
        return "待定短语", True, 0.4
    return "待定语义", True, 0.35


def 是否需要试卷(sentence: str, tokens: list[str], typed_ratio: float) -> str | None:
    """低类型覆盖/长词未定类 → 进试卷，补语义而不是丢弃。"""
    if len(tokens) < 2:
        return None
    if typed_ratio >= 0.5:
        return None
    if len(sentence) >= 12 and typed_ratio < 0.35:
        return "need_semantic_label"
    if any(len(归一化(t)) >= 6 for t in tokens) and typed_ratio < 0.5:
        return "long_token_need_semantic"
    return None


@dataclass
class 内存库存:
    """单次枚举任务的内存累计器。"""
    owner_id: int
    词条: dict[str, dict[str, Any]] = field(default_factory=dict)  # norm -> payload
    出现: list[dict[str, Any]] = field(default_factory=list)
    组合: dict[tuple[str, str], dict[str, Any]] = field(default_factory=dict)
    试卷: list[dict[str, Any]] = field(default_factory=list)
    出现哈希: set[str] = field(default_factory=set)
    试卷哈希: set[str] = field(default_factory=set)
    文档内词: set[str] = field(default_factory=set)
    文档内组合: set[tuple[str, str]] = field(default_factory=set)

    def 新文档(self) -> None:
        self.文档内词.clear()
        self.文档内组合.clear()

    def 记词(self, token: str, candidate_types: list[str] | None = None) -> str:
        surface = (token or "").strip()
        norm = 归一化(surface)
        if not norm:
            return ""
        types = [str(x).strip() for x in (candidate_types or []) if str(x).strip()]
        role, graph_include, conf = 推断语义角色(surface, candidate_types=types)
        new_doc = norm not in self.文档内词
        self.文档内词.add(norm)

        row = self.词条.get(norm)
        if row is None:
            self.词条[norm] = {
                "token": surface[:256],
                "normalized": norm[:256],
                "types": list(types),
                "semantic_role": role,
                "graph_include": bool(graph_include),
                "hit_delta": 1,
                "doc_delta": 1 if new_doc else 0,
                "confidence": float(conf),
            }
        else:
            row["hit_delta"] = int(row["hit_delta"] or 0) + 1
            if new_doc:
                row["doc_delta"] = int(row["doc_delta"] or 0) + 1
            old_types = list(row.get("types") or [])
            for t in types:
                if t not in old_types:
                    old_types.append(t)
            row["types"] = old_types
            new_role, new_graph, new_conf = 推断语义角色(surface, candidate_types=old_types)
            old_role = str(row.get("semantic_role") or "")
            if (not old_role) or old_role.startswith("待定") or old_role in {"弱业务描述"}:
                row["semantic_role"] = new_role
                row["graph_include"] = new_graph
            elif new_role.startswith("业务类型:") and not old_role.startswith("业务类型:"):
                row["semantic_role"] = new_role
                row["graph_include"] = True
            row["confidence"] = max(float(row.get("confidence") or 0), float(new_conf))
            # 保留更长 surface
            if len(surface) > len(str(row.get("token") or "")):
                row["token"] = surface[:256]
        return norm

    def 记出现(
        self,
        *,
        document_id: int,
        page: int | None,
        sentence: str,
        token_norm: str,
        left_token: str | None,
        right_token: str | None,
        position: int | None,
    ) -> bool:
        if not token_norm:
            return False
        source_hash = _hash(
            self.owner_id, document_id, page, token_norm, position, (sentence or "")[:80], left_token, right_token
        )
        if source_hash in self.出现哈希:
            return False
        self.出现哈希.add(source_hash)
        self.出现.append(
            {
                "document_id": int(document_id),
                "page": page,
                "sentence": (sentence or "")[:2000],
                "token_norm": token_norm,
                "left_token": left_token,
                "right_token": right_token,
                "position": position,
                "source_hash": source_hash,
            }
        )
        return True

    def 记组合(self, left_text: str, right_text: str) -> bool:
        ln = 归一化(left_text)
        rn = 归一化(right_text)
        if not ln or not rn:
            return False
        pair = (ln, rn)
        new_doc = pair not in self.文档内组合
        self.文档内组合.add(pair)
        row = self.组合.get(pair)
        if row is None:
            self.组合[pair] = {
                "left_text": left_text,
                "right_text": right_text,
                "left_normalized": ln[:256],
                "right_normalized": rn[:256],
                "combo_text": f"{left_text}+{right_text}"[:512],
                "hit_delta": 1,
                "doc_delta": 1 if new_doc else 0,
            }
        else:
            row["hit_delta"] = int(row["hit_delta"] or 0) + 1
            if new_doc:
                row["doc_delta"] = int(row["doc_delta"] or 0) + 1
        return True

    def 记试卷(
        self,
        *,
        document_id: int,
        page: int | None,
        sentence: str,
        tokens: list[str],
        reason: str,
    ) -> bool:
        source_hash = _hash(self.owner_id, document_id, page, sentence, ",".join(tokens), reason)
        if source_hash in self.试卷哈希:
            return False
        self.试卷哈希.add(source_hash)
        self.试卷.append(
            {
                "document_id": int(document_id),
                "page": page,
                "sentence": (sentence or "")[:2000],
                "tokens": list(tokens),
                "reason": (reason or "")[:128],
                "source_hash": source_hash,
            }
        )
        return True


async def 批量落盘(db: AsyncSession, 库存: 内存库存) -> dict[str, int]:
    """把内存累计一次写进库。返回写入统计。"""
    owner_id = int(库存.owner_id)
    stats = {
        "tokens_upserted": 0,
        "occurrences_written": 0,
        "combos_upserted": 0,
        "exam_items_written": 0,
    }
    if not 库存.词条 and not 库存.出现 and not 库存.组合 and not 库存.试卷:
        return stats

    # 1) 词条批量 UPSERT
    if 库存.词条:
        rows = list(库存.词条.values())
        # 分块，避免参数过大
        chunk = 500
        for i in range(0, len(rows), chunk):
            part = rows[i : i + chunk]
            values_sql = []
            params: dict[str, Any] = {"owner_id": owner_id}
            for j, r in enumerate(part):
                values_sql.append(
                    f"(:owner_id, :token_{j}, :norm_{j}, 'word', CAST(:types_{j} AS json), "
                    f":role_{j}, :graph_{j}, :hit_{j}, :doc_{j}, :conf_{j}, 'candidate', 'enumerate_07a', "
                    f"CAST(:diag_{j} AS json), NOW(), NOW())"
                )
                params[f"token_{j}"] = r["token"]
                params[f"norm_{j}"] = r["normalized"]
                params[f"types_{j}"] = json.dumps(r.get("types") or [], ensure_ascii=False)
                params[f"role_{j}"] = r.get("semantic_role") or "待定语义"
                params[f"graph_{j}"] = bool(r.get("graph_include", True))
                params[f"hit_{j}"] = int(r.get("hit_delta") or 0)
                params[f"doc_{j}"] = int(r.get("doc_delta") or 0)
                params[f"conf_{j}"] = float(r.get("confidence") or 0.0)
                params[f"diag_{j}"] = json.dumps(
                    {
                        "semantic_role": r.get("semantic_role"),
                        "graph_include": r.get("graph_include"),
                        "note": "每个词都有语义角色；graph_include 仅控制主图谱默认是否纳入",
                    },
                    ensure_ascii=False,
                )
            sql = f"""
                INSERT INTO kb_subject_tokens(
                    owner_id, token, normalized, token_kind, candidate_types_json,
                    semantic_role, graph_include, hit_count, doc_count, confidence,
                    status, source, diagnostics_json, created_at, updated_at
                ) VALUES {", ".join(values_sql)}
                ON CONFLICT (owner_id, normalized) DO UPDATE SET
                    hit_count = kb_subject_tokens.hit_count + EXCLUDED.hit_count,
                    doc_count = kb_subject_tokens.doc_count + EXCLUDED.doc_count,
                    confidence = GREATEST(kb_subject_tokens.confidence, EXCLUDED.confidence),
                    candidate_types_json = CASE
                        WHEN kb_subject_tokens.candidate_types_json IS NULL
                             OR kb_subject_tokens.candidate_types_json::text IN ('null','[]')
                        THEN EXCLUDED.candidate_types_json
                        ELSE kb_subject_tokens.candidate_types_json
                    END,
                    semantic_role = CASE
                        WHEN coalesce(kb_subject_tokens.semantic_role, '') = ''
                          OR kb_subject_tokens.semantic_role LIKE '待定%'
                          OR kb_subject_tokens.semantic_role = '弱业务描述'
                        THEN EXCLUDED.semantic_role
                        WHEN EXCLUDED.semantic_role LIKE '业务类型:%'
                          AND coalesce(kb_subject_tokens.semantic_role, '') NOT LIKE '业务类型:%'
                        THEN EXCLUDED.semantic_role
                        ELSE kb_subject_tokens.semantic_role
                    END,
                    graph_include = CASE
                        WHEN EXCLUDED.semantic_role LIKE '业务类型:%' THEN TRUE
                        WHEN coalesce(kb_subject_tokens.semantic_role, '') LIKE '待定%'
                          OR coalesce(kb_subject_tokens.semantic_role, '') = ''
                        THEN EXCLUDED.graph_include
                        ELSE kb_subject_tokens.graph_include
                    END,
                    status = CASE
                        WHEN kb_subject_tokens.status = 'noise' THEN 'candidate'
                        ELSE kb_subject_tokens.status
                    END,
                    token = CASE
                        WHEN char_length(EXCLUDED.token) > char_length(kb_subject_tokens.token)
                        THEN EXCLUDED.token ELSE kb_subject_tokens.token
                    END,
                    updated_at = NOW()
            """
            await db.execute(text(sql), params)
            stats["tokens_upserted"] += len(part)

        # 取 norm -> id 映射
        norms = list(库存.词条.keys())
        norm_to_id: dict[str, int] = {}
        for i in range(0, len(norms), 1000):
            part = norms[i : i + 1000]
            rows = (
                await db.execute(
                    text(
                        """
                        SELECT id, normalized
                        FROM kb_subject_tokens
                        WHERE owner_id = :owner_id AND normalized = ANY(:norms)
                        """
                    ),
                    {"owner_id": owner_id, "norms": part},
                )
            ).all()
            for tid, nrm in rows:
                norm_to_id[str(nrm)] = int(tid)
    else:
        norm_to_id = {}

    # 2) 出现批量插入
    if 库存.出现 and norm_to_id:
        chunk = 800
        for i in range(0, len(库存.出现), chunk):
            part = 库存.出现[i : i + chunk]
            values_sql = []
            params = {"owner_id": owner_id}
            kept = 0
            for j, r in enumerate(part):
                tid = norm_to_id.get(str(r["token_norm"]))
                if not tid:
                    continue
                values_sql.append(
                    f"(:owner_id, :tid_{j}, :doc_{j}, :page_{j}, :sent_{j}, :left_{j}, :right_{j}, "
                    f":pos_{j}, :hash_{j}, 1.0, NOW(), NOW())"
                )
                params[f"tid_{j}"] = int(tid)
                params[f"doc_{j}"] = int(r["document_id"])
                params[f"page_{j}"] = r.get("page")
                params[f"sent_{j}"] = r.get("sentence") or ""
                params[f"left_{j}"] = r.get("left_token")
                params[f"right_{j}"] = r.get("right_token")
                params[f"pos_{j}"] = r.get("position")
                params[f"hash_{j}"] = r.get("source_hash")
                kept += 1
            if not values_sql:
                continue
            sql = f"""
                INSERT INTO kb_subject_occurrences(
                    owner_id, token_id, document_id, page, sentence,
                    left_token, right_token, position, source_hash, weight, created_at, updated_at
                ) VALUES {", ".join(values_sql)}
                ON CONFLICT (owner_id, source_hash) DO NOTHING
            """
            await db.execute(text(sql), params)
            stats["occurrences_written"] += kept

    # 3) 组合批量 UPSERT
    if 库存.组合 and norm_to_id:
        rows = list(库存.组合.values())
        chunk = 500
        for i in range(0, len(rows), chunk):
            part = rows[i : i + chunk]
            values_sql = []
            params = {"owner_id": owner_id}
            for j, r in enumerate(part):
                left_id = norm_to_id.get(str(r["left_normalized"]))
                right_id = norm_to_id.get(str(r["right_normalized"]))
                values_sql.append(
                    f"(:owner_id, :lid_{j}, :rid_{j}, :ln_{j}, :rn_{j}, :ct_{j}, :hit_{j}, :doc_{j}, "
                    f"'candidate', CAST(:diag_{j} AS json), NOW(), NOW())"
                )
                params[f"lid_{j}"] = left_id
                params[f"rid_{j}"] = right_id
                params[f"ln_{j}"] = r["left_normalized"]
                params[f"rn_{j}"] = r["right_normalized"]
                params[f"ct_{j}"] = r["combo_text"]
                params[f"hit_{j}"] = int(r.get("hit_delta") or 0)
                params[f"doc_{j}"] = int(r.get("doc_delta") or 0)
                params[f"diag_{j}"] = json.dumps(
                    {"note": "组合保留完整共现语义，后续可参与召回扩展"},
                    ensure_ascii=False,
                )
            sql = f"""
                INSERT INTO kb_subject_combos(
                    owner_id, left_token_id, right_token_id, left_normalized, right_normalized,
                    combo_text, hit_count, doc_count, status, diagnostics_json, created_at, updated_at
                ) VALUES {", ".join(values_sql)}
                ON CONFLICT (owner_id, left_normalized, right_normalized) DO UPDATE SET
                    hit_count = kb_subject_combos.hit_count + EXCLUDED.hit_count,
                    doc_count = kb_subject_combos.doc_count + EXCLUDED.doc_count,
                    left_token_id = COALESCE(EXCLUDED.left_token_id, kb_subject_combos.left_token_id),
                    right_token_id = COALESCE(EXCLUDED.right_token_id, kb_subject_combos.right_token_id),
                    updated_at = NOW()
            """
            await db.execute(text(sql), params)
            stats["combos_upserted"] += len(part)

    # 4) 试卷批量插入
    if 库存.试卷:
        chunk = 500
        for i in range(0, len(库存.试卷), chunk):
            part = 库存.试卷[i : i + chunk]
            values_sql = []
            params = {"owner_id": owner_id}
            for j, r in enumerate(part):
                values_sql.append(
                    f"(:owner_id, :doc_{j}, :page_{j}, :sent_{j}, CAST(:tok_{j} AS json), :reason_{j}, "
                    f"'pending', :hash_{j}, CAST(:diag_{j} AS json), NOW(), NOW())"
                )
                params[f"doc_{j}"] = int(r["document_id"])
                params[f"page_{j}"] = r.get("page")
                params[f"sent_{j}"] = r.get("sentence") or ""
                params[f"tok_{j}"] = json.dumps(r.get("tokens") or [], ensure_ascii=False)
                params[f"reason_{j}"] = r.get("reason") or ""
                params[f"hash_{j}"] = r.get("source_hash")
                params[f"diag_{j}"] = json.dumps(
                    {"note": "试卷用于补语义，不是删除语义"},
                    ensure_ascii=False,
                )
            sql = f"""
                INSERT INTO kb_subject_exam_items(
                    owner_id, document_id, page, sentence, tokens_json, reason,
                    status, source_hash, diagnostics_json, created_at, updated_at
                ) VALUES {", ".join(values_sql)}
                ON CONFLICT (owner_id, source_hash) DO NOTHING
            """
            await db.execute(text(sql), params)
            stats["exam_items_written"] += len(part)

    await db.commit()
    return stats


# 兼容旧英文名（仅包内过渡）
need_exam = 是否需要试卷
