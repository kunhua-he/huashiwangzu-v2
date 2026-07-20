# -*- coding: utf-8 -*-
"""本地动态分词（节点07A）。

目标：
1. 业务词典从数据库动态载入（禁止业务词硬编码）
2. 对同一句生成多种切法候选
3. 结合历史分类/频次/共现/语义角色打分，选最优切法
4. 不是千篇一律只跑一遍 jieba

数据源（按 owner）：
- kb_entity_dictionary
- kb_terms
- kb_subject_tokens（含 semantic_role / graph_include / hit_count）
- kb_subject_combos（邻接共现）
"""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from modules.knowledge.backend.services.term_tokenizer import (
    产品通名后缀,
    像产品名,
    像机构名,
    匹配通名尾缀,
    机构通名后缀,
    通名类目表,
)

logger = logging.getLogger("v2.knowledge.node07a.tokenize")

# 仅通用虚词 / 计量单位（语言层，非业务词）
_STOP = {
    "的", "了", "和", "与", "及", "或", "在", "是", "为", "对", "等", "中", "上", "下",
    "一个", "我们", "他们", "以及", "通过", "进行", "可以", "没有", "如果", "因为",
    "所以", "但是", "然后", "已经", "自己", "这个", "那个", "什么", "怎么", "哪些",
    "第", "页", "共", "及其", "其中", "其他", "各种", "相关", "以下", "以上", "分别",
}

# 允许保留的单字：虚词连接 + 年月日/计量单位（避免“2021年6月”丢覆盖）
_KEEP_SINGLE = {
    "的", "了",
    "年", "月", "日", "号", "页", "第", "共",
    "瓶", "支", "盒", "袋", "克", "片", "粒", "套", "件", "份", "台", "个",
}

# owner_id -> cache
_CACHE: dict[int, dict[str, Any]] = {}
_CACHE_TTL_SECONDS = 300


@dataclass
class 词信息:
    surface: str
    types: list[str]
    role: str
    graph_include: bool
    hit_count: int
    doc_count: int
    confidence: float
    source_weight: float = 0.3  # 词典/主体沉淀高，裸 terms 低


def 归一化(token: str) -> str:
    t = (token or "").strip().lower()
    t = re.sub(r"\s+", "", t)
    # 含全角标点/书名号/角括号/商标装饰符
    t = re.sub(
        r"[，。！？、；：,.!?;:\"'‘’“”"
        r"（）()【】\[\]《》〈〉<>＜＞「」『』"
        r"·•…—\-_/\\|~～@#￥$%^&*+=`"
        r"★☆●○■□◆◇▲△▼▽※→←↑↓"
        r"®©™°℃"
        r"]+",
        "",
        t,
    )
    return t


def 分句(text_in: str) -> list[str]:
    raw = (text_in or "").replace("\u000b", "\n")
    parts = re.split(r"[\n。！？；;]+", raw)
    out: list[str] = []
    for p in parts:
        s = re.sub(r"\s+", " ", p).strip()
        if len(s) >= 2:
            out.append(s)
    return out


def _empty_info(surface: str) -> 词信息:
    return 词信息(
        surface=surface,
        types=[],
        role="待定语义",
        graph_include=True,
        hit_count=0,
        doc_count=0,
        confidence=0.0,
        source_weight=0.0,
    )


async def 加载词库(db: AsyncSession, owner_id: int, *, force: bool = False) -> dict[str, 词信息]:
    """加载 owner 维度动态词网：词信息 + 共现边。"""
    now = time.time()
    cached = _CACHE.get(int(owner_id))
    if (
        not force
        and cached
        and now - float(cached.get("loaded_at") or 0) < _CACHE_TTL_SECONDS
        and isinstance(cached.get("lexicon"), dict)
    ):
        return cached["lexicon"]

    lexicon: dict[str, 词信息] = {}

    def _upsert(
        token: str,
        *,
        types: list[str] | None = None,
        role: str | None = None,
        graph_include: bool | None = None,
        hit_count: int = 0,
        doc_count: int = 0,
        confidence: float = 0.0,
        source_weight: float = 0.3,
    ) -> None:
        raw = (token or "").strip()
        if not raw:
            return
        norm = 归一化(raw)
        if not norm or norm in _STOP or re.fullmatch(r"\d+", norm):
            return
        old = lexicon.get(norm)
        type_list = [str(x).strip() for x in (types or []) if str(x).strip()]
        if old is None:
            lexicon[norm] = 词信息(
                surface=raw[:256],
                types=type_list,
                role=(role or ("业务类型:" + type_list[0] if type_list else "待定语义")),
                graph_include=True if graph_include is None else bool(graph_include),
                hit_count=int(hit_count or 0),
                doc_count=int(doc_count or 0),
                confidence=float(confidence or 0.0),
                source_weight=float(source_weight or 0.3),
            )
            return
        for t in type_list:
            if t not in old.types:
                old.types.append(t)
        if role and (not old.role or old.role.startswith("待定") or str(role).startswith("业务类型:")):
            old.role = role
        if graph_include is not None:
            old.graph_include = bool(old.graph_include or graph_include)
        old.hit_count = max(int(old.hit_count or 0), int(hit_count or 0))
        old.doc_count = max(int(old.doc_count or 0), int(doc_count or 0))
        old.confidence = max(float(old.confidence or 0.0), float(confidence or 0.0))
        old.source_weight = max(float(old.source_weight or 0.0), float(source_weight or 0.0))
        if len(raw) > len(old.surface):
            old.surface = raw[:256]

    # 1) 实体词典（高质量）
    try:
        rows = (
            await db.execute(
                text(
                    """
                    SELECT name, category
                    FROM kb_entity_dictionary
                    WHERE owner_id = :owner_id
                      AND coalesce(name, '') <> ''
                      AND coalesce(status, 'active') NOT IN ('deleted', 'rejected')
                    """
                ),
                {"owner_id": int(owner_id)},
            )
        ).mappings().all()
        for r in rows:
            cat = str(r.get("category") or "").strip()
            types = [cat] if cat else []
            role = f"业务类型:{cat}" if cat and cat not in {"通用"} else None
            gi = False if cat == "噪音" else True
            _upsert(
                str(r.get("name") or ""),
                types=types,
                role=role,
                graph_include=gi,
                confidence=0.88 if cat else 0.5,
                source_weight=1.0,
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("加载 kb_entity_dictionary 失败 owner=%s: %s", owner_id, exc)

    # 2) terms：只吸收“有类型/高置信”的，避免 70 万无语义碎片污染切法
    try:
        rows = (
            await db.execute(
                text(
                    """
                    SELECT term, term_type, coalesce(confidence, 0) AS confidence
                    FROM kb_terms
                    WHERE owner_id = :owner_id
                      AND coalesce(term, '') <> ''
                      AND coalesce(status, 'active') = 'active'
                      AND (
                        (coalesce(term_type, '') <> '' AND term_type NOT IN ('term', '通用'))
                        OR coalesce(confidence, 0) >= 0.7
                        OR char_length(term) >= 4
                      )
                    LIMIT 200000
                    """
                ),
                {"owner_id": int(owner_id)},
            )
        ).mappings().all()
        for r in rows:
            tt = str(r.get("term_type") or "").strip()
            types = [tt] if tt and tt not in {"term", "通用"} else []
            conf = float(r.get("confidence") or 0.0)
            # 无类型长词只作弱词典，不主导切分
            sw = 0.85 if types else (0.45 if conf >= 0.7 else 0.25)
            role = f"业务类型:{tt}" if types else "待定语义"
            _upsert(
                str(r.get("term") or ""),
                types=types,
                role=role,
                graph_include=True,
                confidence=conf if conf > 0 else (0.5 if types else 0.25),
                source_weight=sw,
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("加载 kb_terms 失败 owner=%s: %s", owner_id, exc)

    # 3) subject tokens（完整语义角色，最高优先）
    try:
        rows = (
            await db.execute(
                text(
                    """
                    SELECT token, candidate_types_json, semantic_role, graph_include,
                           hit_count, doc_count, confidence
                    FROM kb_subject_tokens
                    WHERE owner_id = :owner_id
                      AND coalesce(token, '') <> ''
                    """
                ),
                {"owner_id": int(owner_id)},
            )
        ).mappings().all()
        for r in rows:
            types = r.get("candidate_types_json") or []
            if not isinstance(types, list):
                types = []
            _upsert(
                str(r.get("token") or ""),
                types=[str(x) for x in types if str(x).strip()],
                role=str(r.get("semantic_role") or "") or None,
                graph_include=bool(r.get("graph_include")) if r.get("graph_include") is not None else True,
                hit_count=int(r.get("hit_count") or 0),
                doc_count=int(r.get("doc_count") or 0),
                confidence=float(r.get("confidence") or 0.0),
                source_weight=1.0,
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("加载 kb_subject_tokens 失败 owner=%s: %s", owner_id, exc)

    # 4) 复用 term_tokenizer 通名表：作为结构词注入（非业务硬编码）
    for suf, (cat, _peel) in 通名类目表().items():
        if len(suf) < 2:
            continue
        # 机构通名权重大，便于整并；产品通名次之
        sw = 0.95 if cat in {"机构", "组织"} else 0.75
        _upsert(
            suf,
            types=[cat],
            role=f"业务类型:{cat}",
            graph_include=cat not in {"噪音", "专用章"},
            confidence=0.7,
            source_weight=sw,
        )

    # 5) combos 共现
    combo_score: dict[tuple[str, str], float] = {}
    try:
        rows = (
            await db.execute(
                text(
                    """
                    SELECT left_normalized, right_normalized, hit_count, doc_count
                    FROM kb_subject_combos
                    WHERE owner_id = :owner_id
                    """
                ),
                {"owner_id": int(owner_id)},
            )
        ).mappings().all()
        for r in rows:
            ln = 归一化(str(r.get("left_normalized") or ""))
            rn = 归一化(str(r.get("right_normalized") or ""))
            if not ln or not rn:
                continue
            score = float(r.get("hit_count") or 0) + 0.5 * float(r.get("doc_count") or 0)
            combo_score[(ln, rn)] = max(combo_score.get((ln, rn), 0.0), score)
    except Exception as exc:  # noqa: BLE001
        logger.warning("加载 kb_subject_combos 失败 owner=%s: %s", owner_id, exc)

    # SQL 已完成：立刻结束事务，避免后续 jieba 装配期间 idle-in-transaction 被掐断
    try:
        await db.rollback()
    except Exception:  # noqa: BLE001
        pass

    # 词典键：优先有语义/高权重的词参与动态匹配
    strong_keys = sorted(
        (
            k for k, v in lexicon.items()
            if len(k) >= 2
            and not _looks_non_entity_phrase(v.surface or k)
            and (
                float(v.source_weight or 0) >= 0.8
                or (v.types and len(v.types) > 0)
                or str(v.role or "").startswith("业务类型:")
                or int(v.hit_count or 0) >= 3
            )
        ),
        key=lambda x: (len(x), float(lexicon[x].source_weight or 0), int(lexicon[x].hit_count or 0)),
        reverse=True,
    )
    # 弱词也保留少量长词，避免完全丢失
    # 注意：strong_set 必须在循环外建一次；若写 k not in set(strong_keys) 会每个词重建 3 万级 set，耗时上百秒
    strong_set = set(strong_keys)
    weak_long = sorted(
        (k for k, v in lexicon.items() if len(k) >= 4 and k not in strong_set),
        key=len,
        reverse=True,
    )[:50000]
    dict_keys = strong_keys + weak_long

    # jieba 仍作候选发生器之一：只注入强词（限量，避免装配拖死 DB 会话）
    jieba_mod = None
    try:
        import jieba  # type: ignore

        jieba_mod = jieba
        for w in strong_keys[:20000]:
            jieba.add_word(w)
    except Exception as exc:  # noqa: BLE001
        logger.warning("jieba 不可用，将仅用词典动态匹配: %s", exc)

    org_suffixes = sorted(机构通名后缀(), key=len, reverse=True)
    product_suffixes = sorted(产品通名后缀(), key=len, reverse=True)
    _CACHE[int(owner_id)] = {
        "loaded_at": now,
        "lexicon": lexicon,
        "dict_keys": dict_keys,
        "strong_keys": strong_keys,
        "combo_score": combo_score,
        "org_suffixes": org_suffixes,
        "product_suffixes": product_suffixes,
        "jieba": jieba_mod,
        "size": len(lexicon),
        "strong_size": len(strong_keys),
    }
    logger.info(
        "07A 动态词网已加载 owner=%s lexicon=%s combos=%s",
        owner_id,
        len(lexicon),
        len(combo_score),
    )
    return lexicon


def 词库快照(owner_id: int) -> dict[str, 词信息]:
    cached = (_CACHE.get(int(owner_id)) or {})
    lex = cached.get("lexicon")
    return lex if isinstance(lex, dict) else {}


def _lookup(owner_id: int | None, token: str) -> 词信息:
    if owner_id is None:
        return _empty_info(token)
    lex = 词库快照(int(owner_id))
    info = lex.get(归一化(token))
    if info is None:
        return _empty_info(token)
    return info


def _atomic_pieces(text_in: str) -> list[str]:
    """最小原子：英文数字整词 + 单汉字。仅作合并输入，禁止直接作为最终候选。"""
    return re.findall(r"[A-Za-z0-9][A-Za-z0-9\-.]*|[\u4e00-\u9fff]", text_in or "")


def _is_numeric_token(token: str) -> bool:
    n = 归一化(token)
    return bool(re.fullmatch(r"\d+(\.\d+)?", n or ""))


def _is_bad_single(token: str) -> bool:
    """真正有害的单字碎片：非保留单字、非数字的单汉字/单字母。"""
    n = 归一化(token)
    if not n or n in _KEEP_SINGLE:
        return False
    if _is_numeric_token(n):
        return False
    # 单字母（如品牌 Q）不按有害碎片计
    if re.fullmatch(r"[a-z]", n):
        return False
    return len(n) == 1


def _regex_chunks(text_in: str, owner_id: int | None = None) -> list[str]:
    """多字优先的正则切：先吃库词，再 2 字兜底；绝不吐单字。"""
    s = text_in or ""
    lexicon = 词库快照(int(owner_id)) if owner_id is not None else {}
    strong = set()
    if owner_id is not None:
        cached = (_CACHE.get(int(owner_id)) or {})
        strong = set(cached.get("strong_keys") or [])
    out: list[str] = []
    for m in re.finditer(r"[A-Za-z0-9][A-Za-z0-9\-.]*|[\u4e00-\u9fff]+", s):
        frag = m.group(0)
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9\-.]*", frag):
            out.append(frag)
            continue
        i = 0
        n = len(frag)
        while i < n:
            remain = n - i
            matched = None
            # 最长库词优先（2..min(12,remain)）
            upper = min(12, remain)
            for L in range(upper, 1, -1):
                piece = frag[i : i + L]
                pn = 归一化(piece)
                if pn in strong or (pn in lexicon and float(getattr(lexicon[pn], "source_weight", 0) or 0) >= 0.45):
                    matched = piece
                    break
            if matched is None:
                # 组织后缀：允许较长整吞；产品后缀：最多 6 字，避免描述句整吞
                for L in range(min(14, remain), 2, -1):
                    piece = frag[i : i + L]
                    if _looks_org(piece):
                        matched = piece
                        break
                if matched is None:
                    for L in range(min(6, remain), 2, -1):
                        piece = frag[i : i + L]
                        if _looks_product(piece):
                            matched = piece
                            break
            if matched is None:
                if remain == 1:
                    if out and re.fullmatch(r"[\u4e00-\u9fff]+", out[-1] or ""):
                        out[-1] = out[-1] + frag[i:]
                    # 孤字丢弃
                    break
                # 默认双字，比机械 3/4 更接近中文词感
                take = 2 if remain >= 2 else remain
                if remain == 3:
                    # 3 字整吃，避免 2+1
                    take = 3
                matched = frag[i : i + take]
            out.append(matched)
            i += len(matched)
    return [t for t in out if 归一化(t)]


def _strip_edge_punct(token: str) -> str:
    return re.sub(
        r"^[\s:：,，.。;；、<>＜＞/\\|+\-—_（）()【】\[\]《》〈〉\"'“”‘’★☆●○■□◆◇®©™=…·]+"
        r"|[\s:：,，.。;；、<>＜＞/\\|+\-—_（）()【】\[\]《》〈〉\"'“”‘’★☆●○■□◆◇®©™=…·]+$",
        "",
        token or "",
    )


def _dict_greedy_segment(text_in: str, dict_keys: list[str], max_len: int = 24) -> list[str]:
    """词典最长优先切分（动态，按当前词库）。未知汉字串用多字块，不用单字。"""
    s = text_in or ""
    n = len(s)
    if n == 0:
        return []
    keyset = set(dict_keys)
    out: list[str] = []
    i = 0
    while i < n:
        ch = s[i]
        if ch.isspace() or ch in r":：,，.。;；、<>＜＞/\|+\-—_（）()【】[]《》\"'":
            i += 1
            continue
        # 拉丁/数字串优先整词，避免被短英文词典键切成 Sh/ee/t
        m_lat = re.match(r"[A-Za-z0-9][A-Za-z0-9\-.]*", s[i:])
        if m_lat:
            lat = m_lat.group(0)
            # 仅当整词在库，或长度很短（型号）时才允许再走词典；否则整吃
            lat_norm = 归一化(lat)
            if lat_norm in keyset or len(lat_norm) <= 3:
                out.append(lat)
            else:
                # 允许库内更长短语覆盖（极少见），否则整词
                out.append(lat)
            i += len(lat)
            while i < n and (s[i].isspace() or s[i] in r":：,，.。;；、<>＜＞/\|+\-—_（）()【】[]《》\"'"):
                i += 1
            continue

        matched = None
        upper = min(n, i + max_len)
        for j in range(upper, i, -1):
            frag = _strip_edge_punct(s[i:j])
            if not frag:
                continue
            norm = 归一化(frag)
            if norm in keyset and len(norm) >= 2:
                matched = frag
                break
        if matched is None:
            # 未知汉字：吞 2~4 字，禁止单字原子
            m2 = re.match(r"[\u4e00-\u9fff]{2,4}", s[i:])
            if m2:
                matched = m2.group(0)
            else:
                m1 = re.match(r"[\u4e00-\u9fff]", s[i:])
                if m1:
                    ch1 = m1.group(0)
                    if out and re.fullmatch(r"[\u4e00-\u9fff]+", out[-1]) and len(归一化(out[-1])) < 8:
                        out[-1] = out[-1] + ch1
                        i += 1
                        continue
                    matched = ch1
                else:
                    i += 1
                    continue
        span = len(matched)
        if not s[i:].startswith(matched):
            pos = s.find(matched, i, i + max_len)
            span = (pos - i + len(matched)) if pos >= i else max(1, len(matched))
        out.append(matched)
        i += max(1, span)
        while i < n and (s[i].isspace() or s[i] in r":：,，.。;；、<>＜＞/\|+\-—_（）()【】[]《》\"'"):
            i += 1
    return [t for t in out if _strip_edge_punct(t)]


def _merge_by_dict(tokens: list[str], dict_keys: set[str], max_window: int = 6) -> list[str]:
    """在已有切分上，尝试把相邻原子合并成库词。"""
    if not tokens:
        return []
    out: list[str] = []
    i = 0
    n = len(tokens)
    while i < n:
        merged = None
        max_k = min(max_window, n - i)
        for k in range(max_k, 1, -1):
            frag = "".join(tokens[i : i + k])
            if 归一化(frag) in dict_keys and len(归一化(frag)) >= 2:
                merged = frag
                jump = k
                break
        if merged is None:
            out.append(tokens[i])
            i += 1
        else:
            out.append(merged)
            i += jump
    return out


def _collapse_singles(tokens: list[str], owner_id: int | None = None) -> list[str]:
    """后处理：相邻有害单字优先并入库词/双字；保留年月日/计量单位。"""
    if not tokens:
        return tokens
    lexicon = 词库快照(int(owner_id)) if owner_id is not None else {}
    out: list[str] = []
    i = 0
    n = len(tokens)
    while i < n:
        t = tokens[i]
        tn = 归一化(t)
        # 「第」+ 数字 + 「页」/ 「共」+ 数字 + 「页」
        if tn in {"第", "共"} and i + 1 < n and _is_numeric_token(tokens[i + 1]):
            if i + 2 < n and 归一化(tokens[i + 2]) == "页":
                out.append(t + tokens[i + 1] + tokens[i + 2])
                i += 3
                continue
            out.append(t + tokens[i + 1])
            i += 2
            continue
        # 数字 + 年/月/日/单位：粘成一个计量 token
        if _is_numeric_token(tn) and i + 1 < n:
            nxt = 归一化(tokens[i + 1])
            if nxt in {"年", "月", "日", "号", "页", "瓶", "支", "盒", "袋", "克", "片", "粒", "套", "件", "份", "台", "个", "g", "ml", "kg"}:
                out.append(t + tokens[i + 1])
                i += 2
                continue
        is_cjk_single = _is_bad_single(t) and bool(re.fullmatch(r"[\u4e00-\u9fff]", tn or ""))
        if is_cjk_single:
            run = [t]
            j = i + 1
            while j < n:
                if _is_bad_single(tokens[j]) and re.fullmatch(r"[\u4e00-\u9fff]", 归一化(tokens[j]) or ""):
                    run.append(tokens[j])
                    j += 1
                else:
                    break
            merged = _merge_by_dict(run, set(lexicon.keys()), max_window=min(8, max(2, len(run))))
            packed: list[str] = []
            k = 0
            while k < len(merged):
                if _is_bad_single(merged[k]):
                    if k + 1 < len(merged) and _is_bad_single(merged[k + 1]):
                        packed.append(merged[k] + merged[k + 1])
                        k += 2
                        continue
                    if packed and re.fullmatch(r"[\u4e00-\u9fff]+", packed[-1] or "") and len(归一化(packed[-1])) < 8:
                        packed[-1] = packed[-1] + merged[k]
                    elif out and re.fullmatch(r"[\u4e00-\u9fff]+", out[-1] or "") and len(归一化(out[-1])) < 8:
                        out[-1] = out[-1] + merged[k]
                    # 孤字丢弃
                    k += 1
                else:
                    packed.append(merged[k])
                    k += 1
            out.extend(packed)
            i = j
            continue
        out.append(t)
        i += 1
    return out


def _force_split_by_strong(text_in: str, owner_id: int | None) -> list[str]:
    """强制按强词切分，避免历史误粘长串垄断唯一候选。"""
    if owner_id is None:
        return []
    cached = (_CACHE.get(int(owner_id)) or {})
    strong_keys = list(cached.get("strong_keys") or [])
    s = text_in or ""
    sn = 归一化(s)
    # 明确排除整句本身；限制单段长度，逼出多段切分
    max_piece = min(12, max(2, len(sn) - 1))
    keys = [k for k in strong_keys if 2 <= len(k) <= max_piece and k != sn]
    if not keys:
        return []
    parts = _dict_greedy_segment(s, keys)
    # 若仍是整句或只 1 段，视为失败
    if not parts or (len(parts) == 1 and 归一化(parts[0]) == sn):
        return []
    return _collapse_singles(parts, owner_id)


def _candidate_segmentations(sentence: str, owner_id: int | None) -> list[list[str]]:
    """生成多切法候选。禁止原始单字原子候选进入打分。"""
    s = (sentence or "").strip()
    if not s:
        return []

    cached = _CACHE.get(int(owner_id)) if owner_id is not None else None
    dict_keys: list[str] = list((cached or {}).get("dict_keys") or [])
    keyset = set(dict_keys)
    lexicon = 词库快照(int(owner_id)) if owner_id is not None else {}
    jb = (cached or {}).get("jieba")

    cands: list[list[str]] = []

    sn = 归一化(s)
    whole_info = lexicon.get(sn)
    if whole_info is not None and not _looks_non_entity_phrase(s):
        if _is_business(whole_info) or float(whole_info.source_weight or 0) >= 0.85:
            cands.append([s])

    # 候选A：词典最长优先
    if dict_keys:
        cands.append(_dict_greedy_segment(s, dict_keys))

    # 候选A2：强词强制拆（抑制误粘）
    forced = _force_split_by_strong(s, owner_id)
    if forced:
        cands.append(forced)

    # 候选B：jieba 原始
    if jb is not None:
        try:
            cands.append([t.strip() for t in jb.lcut(s) if t and t.strip()])
        except Exception:  # noqa: BLE001
            pass

    # 候选C：原子切仅用于词典合并，不再把裸 atoms 当候选
    atoms = _atomic_pieces(s)
    if atoms:
        cands.append(_merge_by_dict(atoms, keyset, max_window=8))
        cands.append(_collapse_singles(_merge_by_dict(atoms, keyset, max_window=4), owner_id))

    # 候选D：jieba 后再做一次词典合并
    if jb is not None:
        try:
            base = [t.strip() for t in jb.lcut(s) if t and t.strip()]
            cands.append(_merge_by_dict(base, keyset, max_window=6))
            cands.append(_collapse_singles(base, owner_id))
        except Exception:  # noqa: BLE001
            pass

    # 候选E：多字正则块（覆盖兜底，无单字；带库词最长优先）
    rx = _regex_chunks(s, owner_id)
    if rx:
        cands.append(rx)
        if keyset:
            cands.append(_merge_by_dict(rx, keyset, max_window=6))

    # 清洗 + 去重
    uniq: list[list[str]] = []
    seen: set[tuple[str, ...]] = set()
    for cand in cands:
        cleaned: list[str] = []
        for t in cand:
            t2 = _strip_edge_punct(t)
            n = 归一化(t2)
            if not n:
                continue
            # 保留“的/了/年/月/瓶…”等单字，避免覆盖率与计量语义丢失
            if n in _STOP and n not in _KEEP_SINGLE:
                continue
            if re.fullmatch(r"\d+(\.\d+)?", n):
                cleaned.append(t2)
                continue
            # 清洗阶段丢弃未知有害单字；保留计量/虚词单字
            if len(n) == 1 and n not in keyset and n not in _KEEP_SINGLE and not re.fullmatch(r"[a-z]", n):
                continue
            cleaned.append(t2)
        if not cleaned:
            continue
        cleaned = _collapse_singles(cleaned, owner_id)
        key = tuple(归一化(x) for x in cleaned)
        if key in seen:
            continue
        seen.add(key)
        uniq.append(cleaned)
    return uniq



# 可信业务类型（历史脏标签不主导切分）
_TRUSTED_TYPES = {
    "品牌", "产品", "组织", "机构", "人物", "成分", "功效", "系列", "品类", "规格", "时间",
}
_NOISY_TYPES = {
    "部门岗位", "检验报告", "专用章", "人名", "标准法规", "噪音", "通用", "term",
    "营销内容", "视觉素材",
}

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
_WEAK_ORG_SUFFIXES = {"门店", "分公司", "集团"}


def _field_glue_count(text_in: str) -> int:
    raw = str(text_in or "")
    norm = 归一化(raw)
    return sum(1 for h in _FIELD_GLUE_HINTS if h in raw or 归一化(h) in norm)


def _looks_non_entity_phrase(token: str) -> bool:
    """历史脏词/表格表头/页面描述，不能作为强业务词反哺切分。"""
    raw = str(token or "").strip()
    norm = 归一化(raw)
    if len(norm) < 12:
        return False
    if _field_glue_count(raw) >= 2:
        return True
    if _SENTENCE_GLUE_RE.search(raw) and not (_looks_org(raw) or _looks_product(raw, allow_long=True)):
        return True
    if len(norm) >= 24 and not (_looks_org(raw) or _looks_product(raw, allow_long=True)):
        return True
    return False


def _org_suffixes(owner_id: int | None = None) -> list[str]:
    """机构通名：优先缓存，否则复用 term_tokenizer。"""
    if owner_id is not None:
        cached = (_CACHE.get(int(owner_id)) or {})
        got = cached.get("org_suffixes")
        if isinstance(got, list) and got:
            return got
    return 机构通名后缀()


def _product_suffixes(owner_id: int | None = None) -> list[str]:
    if owner_id is not None:
        cached = (_CACHE.get(int(owner_id)) or {})
        got = cached.get("product_suffixes")
        if isinstance(got, list) and got:
            return got
    return 产品通名后缀()


def _trusted_types(types: list[str] | None) -> list[str]:
    out: list[str] = []
    for t in types or []:
        t2 = str(t).strip()
        if not t2 or t2 in _NOISY_TYPES:
            continue
        if t2 in _TRUSTED_TYPES or t2.startswith("业务类型:"):
            if t2 not in out:
                out.append(t2)
    return out


def _is_business(info: 词信息) -> bool:
    role = str(info.role or "")
    if role.startswith("业务类型:"):
        tail = role.split(":", 1)[-1]
        if tail not in _NOISY_TYPES:
            return True
    return bool(_trusted_types(info.types))


def _looks_product(token: str, *, allow_long: bool = False) -> bool:
    """产品启发：短专名/库内词可整认；长描述尾缀带「精华液」等不当整产品。"""
    n = 归一化(token)
    if not n:
        return False
    hit = 匹配通名尾缀(token)
    if not hit:
        return False
    suf, cat, _ = hit
    if cat != "产品":
        return False
    # 通名本身
    if n == 归一化(suf):
        return True
    # 过长描述串只是“以产品通名结尾”，不是产品专名
    if not allow_long and len(n) > 8:
        return False
    # 单字通名（霜/液/乳…）要求主体更短更像品名
    if len(归一化(suf)) == 1 and len(n) > 6:
        return False
    return 像产品名(token) or len(n) >= 3


def _looks_org(token: str) -> bool:
    # 仍像机构的超长表头/描述串不算组织名。
    if _field_glue_count(token) >= 2:
        return False
    hit = 匹配通名尾缀(token)
    if hit:
        suf, cat, _ = hit
        norm = 归一化(token)
        if cat in {"机构", "组织"} and suf in _WEAK_ORG_SUFFIXES:
            return 5 <= len(norm) <= 16 and not _SENTENCE_GLUE_RE.search(str(token or ""))
    return 像机构名(token)


def _split_overlong_token(token: str, owner_id: int | None = None) -> list[str]:
    """非机构超长串强制再切，避免整句描述落成一词。"""
    t = _strip_edge_punct(token)
    n = 归一化(t)
    if not t:
        return []
    if _looks_org(t):
        return [t]
    # 英文长词/编号可保留
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9\-_.]{0,40}", t or ""):
        return [t]
    if len(n) <= 12:
        return [t]
    # 先产品剥尾，再正则/词典
    peeled = _peel_product_tail([t], owner_id)
    if len(peeled) >= 2:
        return peeled
    parts = _regex_chunks(t, owner_id) or []
    if not parts:
        # 硬双字
        parts = [t[i : i + 2] for i in range(0, len(t), 2) if t[i : i + 2].strip()]
    # 仍超长则继续拆
    out: list[str] = []
    for p in parts:
        pn = 归一化(p)
        if len(pn) > 12 and not _looks_org(p):
            out.extend(_regex_chunks(p, None) or [p])
        else:
            out.append(p)
    return [_strip_edge_punct(x) for x in out if _strip_edge_punct(x)]


# 产品前的无意义粘连前缀（装洗衣液/等洗衣液/的面霜…）
_产品垃圾前缀 = {
    "装", "等", "的", "及", "和", "与", "为", "有", "在", "是", "其", "该", "本",
    "一", "二", "三", "这", "那", "些", "瓶", "支", "盒", "袋", "件", "个",
}


def _peel_product_tail(tokens: list[str], owner_id: int | None = None) -> list[str]:
    """把『周围环绕金色精华液/装洗衣液』拆成前缀 + 产品通名尾。"""
    if not tokens:
        return tokens
    lexicon = 词库快照(int(owner_id)) if owner_id is not None else {}
    out: list[str] = []
    for t in tokens:
        t2 = _strip_edge_punct(t)
        n = 归一化(t2)
        if not t2:
            continue
        hit = 匹配通名尾缀(t2)
        if not hit:
            out.append(t2)
            continue
        suf, cat, _ = hit
        if cat != "产品":
            out.append(t2)
            continue
        sn = 归一化(suf)
        # 通名本身
        if n == sn:
            out.append(t2)
            continue

        # 对齐 head/tail（优先多字产品通名）
        head, tail = None, None
        multi = sorted([x for x in _product_suffixes(owner_id) if len(x) >= 2], key=len, reverse=True)
        for ms in multi:
            mn = 归一化(ms)
            if n.endswith(mn) and len(n) > len(mn):
                if t2.endswith(ms):
                    head, tail = t2[: -len(ms)], ms
                else:
                    head, tail = t2[: -len(mn)], t2[-len(mn) :]
                sn = mn
                break
        if tail is None and len(sn) >= 2 and n.endswith(sn):
            if t2.endswith(suf):
                head, tail = t2[: -len(suf)], suf
            else:
                head, tail = t2[: -len(sn)], t2[-len(sn) :]
        if tail is None and len(sn) == 1 and len(n) > 6:
            head, tail = t2[:-1], t2[-1]
        if tail is None or head is None:
            out.append(t2)
            continue

        head = _strip_edge_punct(head)
        hn = 归一化(head)
        if not hn:
            out.append(tail)
            continue

        # 垃圾短前缀：只留产品
        if hn in _产品垃圾前缀 or (len(hn) == 1 and hn not in lexicon):
            # 计量单位前缀并到前一 token 更合理，这里先单独保留短单位
            if hn in {"瓶", "支", "盒", "袋", "件", "个"} and out:
                out[-1] = out[-1] + head
            out.append(tail)
            continue

        # 库内高权短专名（≤8）且前缀不像垃圾：保留整词（肌密精华液/悠源沁润霜）
        info = lexicon.get(n)
        if (
            info is not None
            and float(info.source_weight or 0) >= 0.85
            and len(n) <= 8
            and len(hn) >= 2
            and hn not in _产品垃圾前缀
        ):
            out.append(t2)
            continue

        # 短专名形态：2~4 字品牌/系列 + 多字产品通名 → 保留整词
        if 2 <= len(hn) <= 4 and len(sn) >= 2 and len(n) <= 8 and hn not in _产品垃圾前缀:
            # 前缀全是汉字且不像动词短语
            if re.fullmatch(r"[\u4e00-\u9fff]{2,4}", hn or "") and not any(
                hn.endswith(x) for x in ("环绕", "陈列", "展示", "可见", "突出", "使用", "添加")
            ):
                out.append(t2)
                continue

        # 前缀过长或描述性：剥开
        if len(n) <= max(len(sn) + 1, 4) and hn not in _产品垃圾前缀:
            out.append(t2)
            continue

        head_parts = _regex_chunks(head, owner_id) or [head]
        fixed: list[str] = []
        for hp in head_parts:
            hpn = 归一化(hp)
            hh = 匹配通名尾缀(hp)
            if len(hpn) > 8 and hh and hh[1] == "产品":
                fixed.extend(_peel_product_tail([hp], owner_id) or [hp])
            else:
                fixed.append(hp)
        out.extend([_strip_edge_punct(x) for x in fixed if _strip_edge_punct(x)])
        out.append(tail)
    return [x for x in out if x]


def _coverage(tokens: list[str], sentence: str) -> float:
    """覆盖率忽略通用虚词与装饰序号，避免误判丢字。"""
    def _content_chars(s: str) -> str:
        n = 归一化(s)
        # 章节序号/装饰字不计入（（四）/一、等）
        n = re.sub(r"^[一二三四五六七八九十百千零〇]+", "", n)
        n = re.sub(r"(?<=^)[ivxlcdm]+", "", n)
        for w in ("的", "了", "和", "与", "及", "或", "在", "是", "为", "对", "等"):
            n = n.replace(w, "")
        return n

    sent_norm = _content_chars(sentence)
    if not sent_norm:
        return 1.0
    joined = _content_chars("".join(tokens))
    if not joined:
        return 0.0
    # 子串覆盖：允许 tokens 顺序拼接后是原文内容子序列的近似
    ratio = min(len(joined), len(sent_norm)) / max(len(sent_norm), 1)
    # 若几乎覆盖但差 1~2 个装饰/连接字，给一点容差
    if ratio >= 0.92 and abs(len(sent_norm) - len(joined)) <= 2:
        return max(ratio, 0.96)
    return ratio


def _can_split_into_known_parts(token: str, owner_id: int | None, min_parts: int = 2) -> bool:
    """若长串可被拆成多个库内已知片段，说明更可能是误粘，应倾向拆开。"""
    if owner_id is None:
        return False
    norm = 归一化(token)
    if len(norm) < 4:
        return False
    cached = (_CACHE.get(int(owner_id)) or {})
    strong = set(cached.get("strong_keys") or [])
    if not strong:
        return False
    n = len(norm)
    best = [0] + [-1] * n
    for i in range(n):
        if best[i] < 0:
            continue
        for j in range(i + 1, min(n, i + 12) + 1):
            frag = norm[i:j]
            if frag in strong:
                if len(frag) == 1:
                    continue
                best[j] = max(best[j], best[i] + 1)
    return best[n] >= min_parts


def _score_segmentation(tokens: list[str], owner_id: int | None, sentence: str = "") -> float:
    """按平均质量 + 覆盖率硬约束 + 整词保护打分。"""
    if not tokens:
        return -1e9

    cached = (_CACHE.get(int(owner_id)) or {}) if owner_id is not None else {}
    combo_score: dict[tuple[str, str], float] = (cached or {}).get("combo_score") or {}
    lexicon = 词库快照(int(owner_id)) if owner_id is not None else {}

    n = len(tokens)
    token_scores: list[float] = []
    covered_norms: list[str] = []
    max_business_len = 0
    whole_entity_bonus = 0.0
    product_org_hits = 0

    for i, tok in enumerate(tokens):
        info = _lookup(owner_id, tok)
        norm = 归一化(tok)
        covered_norms.append(norm)
        in_lex = norm in lexicon
        s = 0.0

        # 历史信号弱化，避免脏频次带偏
        s += min(float(info.hit_count or 0), 40.0) * 0.012
        s += min(float(info.doc_count or 0), 20.0) * 0.025
        s += float(info.confidence or 0.0) * 0.45
        s += float(info.source_weight or 0.0) * 0.8

        trusted = _trusted_types(info.types)
        role = str(info.role or "")

        if trusted or (_is_business(info) and not any(t in _NOISY_TYPES for t in (info.types or []))):
            s += 4.5 + min(len(norm), 18) * 0.28
            max_business_len = max(max_business_len, len(norm))
            if len(norm) >= 6:
                whole_entity_bonus += 8.0 + min(len(norm), 20) * 0.35
        elif _looks_org(tok) or _looks_product(tok):
            s += 5.0 + min(len(norm), 18) * 0.3
            product_org_hits += 1
            whole_entity_bonus += 9.0
        elif in_lex and float(info.source_weight or 0) >= 0.85:
            s += 1.3 + min(len(norm), 12) * 0.06
        elif in_lex:
            s += 0.3
        elif role in {"修饰限定", "功能连接", "计量数值", "模板套话"}:
            s += 0.2
        else:
            s += 0.15

        # 脏类型降权
        if info.types and not trusted and any(t in _NOISY_TYPES for t in info.types):
            s -= 1.3

        if _is_bad_single(tok):
            s -= 2.5
        elif len(norm) == 1 and not _is_numeric_token(tok):
            s -= 0.4  # 的/了 等允许
        # 机械拼接块（无库支持的 3~4 字未知串）略降权，让 jieba/词典胜出
        if 3 <= len(norm) <= 4 and not in_lex and not trusted and not _looks_product(tok) and not _looks_org(tok):
            s -= 0.6
        if len(norm) >= 14 and _looks_non_entity_phrase(tok):
            s -= 12.0
        elif len(norm) >= 14 and not in_lex and not _looks_org(tok) and not _looks_product(tok):
            s -= 2.8

        if i + 1 < n:
            nxt = 归一化(tokens[i + 1])
            cs = float(combo_score.get((norm, nxt), 0.0))
            if cs > 0:
                s += min(cs, 30.0) * 0.015

        token_scores.append(s)

    avg = sum(token_scores) / max(len(token_scores), 1)
    score = avg * 8.0

    cov = _coverage(tokens, sentence)
    score += cov * 14.0
    if cov < 0.98:
        score -= (0.98 - cov) * 110.0
    if cov < 0.9:
        score -= 35.0

    score += min(whole_entity_bonus, 20.0)
    score += product_org_hits * 3.0
    score += min(max_business_len, 20) * 0.12
    score -= max(0, n - 7) * 0.7

    # 过粗整句粘连
    if n == 1:
        only = _lookup(owner_id, tokens[0])
        if not _is_business(only) and not _looks_org(tokens[0]) and not _looks_product(tokens[0]):
            score -= 30.0
        if _looks_non_entity_phrase(tokens[0]):
            score -= 55.0
        if _can_split_into_known_parts(tokens[0], owner_id, min_parts=2):
            score -= 45.0
        sent_norm = 归一化(sentence)
        if sent_norm and len(归一化(tokens[0])) < len(sent_norm) * 0.85:
            score -= 25.0

    # 公司/产品被拆碎惩罚（通名来自 term_tokenizer，不写死业务词）
    sent = sentence or ""
    org_sufs = _org_suffixes(owner_id)
    prod_sufs = _product_suffixes(owner_id)
    if any(suf in sent for suf in org_sufs):
        has_full_org = any(_looks_org(t) for t in tokens)
        if not has_full_org:
            if any(匹配通名尾缀(t) and 匹配通名尾缀(t)[1] in {"机构", "组织"} and 归一化(t) in set(org_sufs) for t in tokens):
                score -= 18.0
            else:
                score -= 8.0
        else:
            score += 6.0
    if any(suf in sent for suf in prod_sufs):
        if not any(_looks_product(t) for t in tokens):
            score -= 6.0
        else:
            score += 3.0

    # 拉丁词被切成 2 字母碎片
    for tok in tokens:
        nn = 归一化(tok)
        if re.fullmatch(r"[a-z]{1,2}", nn or ""):
            score -= 4.0

    for tok in tokens:
        nn = 归一化(tok)
        if len(nn) >= 6 and _can_split_into_known_parts(tok, owner_id, min_parts=2):
            info = _lookup(owner_id, tok)
            if not ((_is_business(info) or _looks_org(tok) or _looks_product(tok)) and float(info.source_weight or 0) >= 0.85):
                score -= 10.0

    return score


def _peel_embedded_org(tokens: list[str], owner_id: int | None = None) -> list[str]:
    """从过长粘连串中剥出嵌入的机构全称，如前缀『送检单位为』+ 公司名。"""
    if not tokens:
        return tokens
    out: list[str] = []
    for t in tokens:
        t2 = _strip_edge_punct(t)
        if not t2:
            continue
        if len(归一化(t2)) < 8 or _looks_org(t2):
            out.append(t2)
            continue
        # 找最长机构后缀子串
        best = None  # (prefix, org)
        n = len(t2)
        for i in range(n):
            sub = _strip_edge_punct(t2[i:])
            if _looks_org(sub) and len(归一化(sub)) >= 6:
                pref = _strip_edge_punct(t2[:i])
                # 去掉前缀末尾连接字
                pref = re.sub(r"[为是：:与和及的]+$", "", pref or "")
                best = (pref, sub)
                break  # 最早起点 = 最长机构名
        if best is None:
            out.append(t2)
            continue
        pref, org = best
        if pref and len(归一化(pref)) >= 2:
            # 前缀再走多字切，避免再粘回去
            pref_parts = _regex_chunks(pref, owner_id) or [pref]
            out.extend([_strip_edge_punct(x) for x in pref_parts if _strip_edge_punct(x)])
        out.append(org)
    return [x for x in out if x]


def _merge_org_spans(tokens: list[str], sentence: str, owner_id: int | None = None) -> list[str]:
    """把被拆开的公司名/组织名尽量并回整词。通名来自 term_tokenizer，不写省市业务表。"""
    if not tokens:
        return tokens
    sent = sentence or ""
    org_sufs = _org_suffixes(owner_id)
    if not org_sufs or not any(suf in sent for suf in org_sufs):
        return tokens

    org_suf_set = set(org_sufs)
    # 已有完整组织 token 且没有孤立机构通名则跳过
    isolated_tail = any(归一化(t) in org_suf_set for t in tokens)
    if any(_looks_org(t) for t in tokens) and not isolated_tail:
        return tokens

    out = list(tokens)
    i = 0
    while i < len(out):
        n = 归一化(out[i])
        is_org_tail = n in org_suf_set or any(n.endswith(suf) for suf in org_sufs)
        if not is_org_tail:
            i += 1
            continue

        best_left = None
        max_back = min(i, 8)
        for back in range(1, max_back + 1):
            left = i - back
            cand = "".join(out[left : i + 1])
            cn = 归一化(cand)
            if _looks_org(cand) or (any(cn.endswith(suf) for suf in org_sufs) and len(cn) >= 6):
                best_left = left
                continue
        if best_left is None and i > 0 and n in org_suf_set:
            # 无省市硬表：向前吞 1~4 段，直到形成 looks_org 或长度够
            take = min(4, i)
            best_left = i - take
            for back in range(1, take + 1):
                left = i - back
                cand = "".join(out[left : i + 1])
                if _looks_org(cand) or len(归一化(cand)) >= 8:
                    best_left = left
                    break

        if best_left is not None and best_left < i:
            cand = "".join(out[best_left : i + 1])
            out = out[:best_left] + [cand] + out[i + 1 :]
            i = best_left
        i += 1

    # 二次：夹心短段 + 机构通名
    j = 0
    while j < len(out) - 2:
        b, c = 归一化(out[j + 1]), 归一化(out[j + 2])
        if c in org_suf_set and len(b) <= 4:
            cand = out[j] + out[j + 1] + out[j + 2]
            if _looks_org(cand) or len(归一化(cand)) >= 8:
                out = out[:j] + [cand] + out[j + 3 :]
                continue
        if b in org_suf_set:
            cand = out[j] + out[j + 1]
            out = out[:j] + [cand] + out[j + 2 :]
            continue
        j += 1
    return out


def _multi_char_fallback(sentence: str, owner_id: int | None) -> list[str]:
    """覆盖不足时的多字回退：强词拆 > 正则块 > 词典合并，绝不回退单字原子。"""
    forced = _force_split_by_strong(sentence, owner_id)
    if forced and _coverage(forced, sentence) >= 0.9:
        return _collapse_singles(forced, owner_id)

    cached = (_CACHE.get(int(owner_id)) or {}) if owner_id is not None else {}
    keyset = set(cached.get("dict_keys") or [])
    rx = _regex_chunks(sentence, owner_id)
    if rx:
        merged = _merge_by_dict(rx, keyset, max_window=6) if keyset else rx
        merged = _collapse_singles(merged, owner_id)
        if _coverage(merged, sentence) >= 0.9:
            return merged
        return merged

    if keyset:
        greedy = _dict_greedy_segment(sentence, list(keyset))
        if greedy:
            return _collapse_singles(greedy, owner_id)
    return _collapse_singles(rx or [], owner_id)


def _repair_uncovered_tail(tokens: list[str], sentence: str, owner_id: int | None) -> list[str]:
    """若切分后覆盖不足，整句切换到更优多字候选；禁止单字原子与重复拼接。"""
    if not tokens or not sentence:
        return tokens
    if _coverage(tokens, sentence) >= 0.96:
        return _collapse_singles(tokens, owner_id)

    fallback = _multi_char_fallback(sentence, owner_id)
    if not fallback:
        return _collapse_singles(tokens, owner_id)

    def _bad_count(ts: list[str]) -> int:
        return sum(1 for t in ts if _is_bad_single(t))

    tok_cov = _coverage(tokens, sentence)
    fb_cov = _coverage(fallback, sentence)
    # 整句替换优先于拼接，避免“原切 + 再切”重复
    if fb_cov > tok_cov + 0.01 and _bad_count(fallback) <= _bad_count(tokens) + 1:
        return _collapse_singles(fallback, owner_id)
    if fb_cov >= 0.96 and _bad_count(fallback) == 0 and tok_cov < 0.96:
        return _collapse_singles(fallback, owner_id)
    if fb_cov >= tok_cov and _bad_count(fallback) < _bad_count(tokens):
        return _collapse_singles(fallback, owner_id)
    return _collapse_singles(tokens, owner_id)


def 分词(sentence: str, owner_id: int | None = None) -> list[str]:
    """动态分词：多候选 + 历史语义打分 + 覆盖率硬回退。"""
    s = (sentence or "").strip()
    if not s:
        return []

    whole_norm = 归一化(s)
    if owner_id is not None:
        whole_info = 词库快照(int(owner_id)).get(whole_norm)
        if (
            whole_info is not None
            and not _looks_non_entity_phrase(s)
            and (_is_business(whole_info) or float(whole_info.source_weight or 0) >= 0.85)
            and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9\s_.\-]{1,64}", s)
        ):
            return [s]

    cands = _candidate_segmentations(s, owner_id)
    if not cands:
        return _multi_char_fallback(s, owner_id) or [
            t for t in re.findall(r"[A-Za-z0-9\-]+|[\u4e00-\u9fff]{2,8}", s)
            if 归一化(t) not in _STOP
        ]

    def _single_ratio(ts: list[str]) -> float:
        if not ts:
            return 1.0
        bad = sum(1 for t in ts if _is_bad_single(t))
        return bad / max(len(ts), 1)

    def _mech_ratio(ts: list[str]) -> float:
        """未知 2 字块占比：描述句机械切的信号。"""
        if not ts:
            return 1.0
        lexicon = 词库快照(int(owner_id)) if owner_id is not None else {}
        bad = 0
        for t in ts:
            n = 归一化(t)
            if len(n) != 2:
                continue
            if n in lexicon or n in _STOP or _is_numeric_token(n):
                continue
            if re.fullmatch(r"[a-z0-9]+", n or ""):
                continue
            bad += 1
        return bad / max(len(ts), 1)

    def _biz_hits(ts: list[str]) -> int:
        n = 0
        for t in ts:
            info = _lookup(owner_id, t)
            if _is_business(info) or _looks_org(t) or _looks_product(t):
                n += 1
        return n

    scored = []
    for c in cands:
        sc = _score_segmentation(c, owner_id, sentence=s)
        cov = _coverage(c, s)
        # 有害单字占比高的候选额外降权
        sc -= _single_ratio(c) * 40.0
        # 长描述句：机械双字过多时降权，让 jieba 自然切胜出
        if len(归一化(s)) >= 16 and _biz_hits(c) == 0:
            sc -= _mech_ratio(c) * 12.0
        scored.append((c, sc, cov))
    scored.sort(key=lambda x: x[1], reverse=True)
    best_tokens, best_score, best_cov = scored[0]

    # 覆盖率硬回退：优先“高覆盖 + 少单字 + 可接受分数”
    if best_cov < 0.96 or _single_ratio(best_tokens) > 0.25:
        by_cov = sorted(
            scored,
            key=lambda x: (x[2] - _single_ratio(x[0]) * 0.3, x[1]),
            reverse=True,
        )
        chosen = False
        for tokens, sc, cov in by_cov:
            if (
                cov >= 0.96
                and _single_ratio(tokens) <= 0.2
                and sc > best_score - 30
                and not (len(tokens) == 1 and _can_split_into_known_parts(tokens[0], owner_id, min_parts=2))
            ):
                best_tokens, best_score, best_cov = tokens, sc, cov
                chosen = True
                break
        if not chosen:
            for tokens, sc, cov in by_cov:
                if cov >= 0.9 and len(tokens) >= 2 and _single_ratio(tokens) <= 0.25:
                    best_tokens, best_score, best_cov = tokens, sc, cov
                    chosen = True
                    break
        if not chosen:
            best_tokens, best_score, best_cov = by_cov[0]

    # 整句粘连且可拆，强制换多段候选
    if len(best_tokens) == 1 and _can_split_into_known_parts(best_tokens[0], owner_id, min_parts=2):
        for tokens, sc, cov in sorted(scored, key=lambda x: x[1], reverse=True):
            if len(tokens) >= 2 and cov >= 0.9 and _single_ratio(tokens) <= 0.25:
                best_tokens = tokens
                break

    # 仍覆盖不足：多字补切（整句替换，不拼接）
    if _coverage(best_tokens, s) < 0.96:
        best_tokens = _repair_uncovered_tail(best_tokens, s, owner_id)

    # 最终单字塌缩 + 边标点剥离
    best_tokens = [_strip_edge_punct(t) for t in _collapse_singles(best_tokens, owner_id) if _strip_edge_punct(t)]

    # 后处理：产品描述粘连剥尾 → 超长硬拆 → 嵌入机构名剥出 → 公司名整并
    best_tokens = _peel_product_tail(best_tokens, owner_id)
    expanded: list[str] = []
    for t in best_tokens:
        expanded.extend(_split_overlong_token(t, owner_id))
    best_tokens = expanded
    best_tokens = _peel_embedded_org(best_tokens, owner_id)
    best_tokens = _merge_org_spans(best_tokens, s, owner_id)
    best_tokens = [_strip_edge_punct(t) for t in best_tokens if _strip_edge_punct(t)]

    # 若塌缩后覆盖崩了，用多字回退
    if _coverage(best_tokens, s) < 0.9:
        fb = _multi_char_fallback(s, owner_id)
        if fb and _coverage(fb, s) > _coverage(best_tokens, s):
            best_tokens = _peel_product_tail(fb, owner_id)
            expanded = []
            for t in best_tokens:
                expanded.extend(_split_overlong_token(t, owner_id))
            best_tokens = expanded
            best_tokens = _peel_embedded_org(best_tokens, owner_id)
            best_tokens = _merge_org_spans(best_tokens, s, owner_id)
            best_tokens = [_strip_edge_punct(t) for t in best_tokens if _strip_edge_punct(t)]

    return best_tokens


def 分词带诊断(sentence: str, owner_id: int | None = None) -> dict[str, Any]:
    """调试用：返回候选与得分。"""
    s = (sentence or "").strip()
    cands = _candidate_segmentations(s, owner_id)
    scored = []
    for c in cands:
        scored.append({
            "tokens": c,
            "score": round(_score_segmentation(c, owner_id, sentence=s), 4),
            "coverage": round(_coverage(c, s), 4),
        })
    scored.sort(key=lambda x: x["score"], reverse=True)
    best = 分词(s, owner_id)
    return {"sentence": sentence, "best": best, "candidates": scored[:8]}


def 候选类型猜测(token: str, owner_id: int | None = None) -> list[str]:
    """只返回可信业务类型；脏标签不作为主类型输出。"""
    info = _lookup(owner_id, token)
    trusted = _trusted_types(info.types)
    role = str(info.role or "")
    if role.startswith("业务类型:"):
        role_type = role.split(":", 1)[-1].strip()
        if role_type and role_type not in _NOISY_TYPES and role_type not in trusted:
            trusted.insert(0, role_type)
    if trusted:
        return trusted
    n = 归一化(token)
    hit = 匹配通名尾缀(token)
    if hit:
        suf, cat, _ = hit
        if cat in {"机构", "组织"}:
            if suf in _WEAK_ORG_SUFFIXES and not _looks_org(token):
                return []
            return ["组织"]
        if cat == "产品":
            return ["产品"]
        if cat and cat not in _NOISY_TYPES:
            return [cat]
    if _looks_org(token):
        return ["组织"]
    if _looks_product(token):
        return ["产品"]
    if re.fullmatch(r"\d{4}-\d{1,2}-\d{1,2}", n) or re.fullmatch(r"\d{4}年\d{1,2}月\d{1,2}日", n):
        return ["时间"]
    weak = [t for t in (info.types or []) if str(t) not in _NOISY_TYPES]
    return weak


async def 确保词库(db: AsyncSession, owner_id: int) -> dict[str, 词信息]:
    return await 加载词库(db, owner_id, force=False)
