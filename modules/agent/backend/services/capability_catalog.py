from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import math
import re
import time
from collections import Counter
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path

from app.services.module_registry import (
    authorized_capability_snapshot,
    call_capability_as_system,
)

from ..engine.file_state_lock import read_json_locked, update_json_locked

EmbeddingFn = Callable[[list[str]], Awaitable[list[list[float]]]]

_WORD_RE = re.compile(r"[A-Za-z0-9]+|[\u4e00-\u9fff]")
_CACHE_DIR = Path(__file__).resolve().parents[4] / "backend" / "data" / "runtime" / "agent_capability_index"
_RRF_K = 60
logger = logging.getLogger("v2.agent").getChild("services.capability_catalog")

# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
# \u70ed\u7f13\u5b58\uff1aauthorized_capability_snapshot \u5185\u5b58\u7ea7\u7f13\u5b58
# \u540c\u4e00\u7528\u6237\u77ed\u65f6\u95f4\u5185\uff0860\u79d2\uff09\u591a\u6b21\u8c03\u7528\u76f4\u63a5\u8fd4\u56de\uff0c\u4e0d\u91cd\u590d\u505aSQL+\u5d4c\u5165
# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
_SNAPSHOT_CACHE: dict[int, tuple[float, dict]] = {}  # user_id \u2192 (timestamp, snapshot)
_SNAPSHOT_CACHE_TTL = 60.0  # \u79d2


async def _cached_capability_snapshot(*, user_id: int) -> dict:
    """\u5e26\u5185\u5b58\u7f13\u5b58\u7684 authorized_capability_snapshot"""
    now = time.time()
    cached = _SNAPSHOT_CACHE.get(user_id)
    if cached and (now - cached[0]) < _SNAPSHOT_CACHE_TTL:
        return cached[1]
    snapshot = await authorized_capability_snapshot(user_id=user_id)
    _SNAPSHOT_CACHE[user_id] = (now, snapshot)
    return snapshot


def invalidate_snapshot_cache(user_id: int | None = None) -> None:
    """\u624b\u52a8\u6e05\u9664\u7f13\u5b58\uff08\u6743\u9650\u53d8\u66f4\u65f6\u8c03\u7528\uff09"""
    if user_id is None:
        _SNAPSHOT_CACHE.clear()
    else:
        _SNAPSHOT_CACHE.pop(user_id, None)


# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
# \u5feb\u901f\u901a\u9053\uff1a\u9ad8\u9891\u67e5\u8be2\u76f4\u63a5\u547d\u4e2d\u80fd\u529b\uff0c\u8df3\u8fc7\u5168\u91cf\u6392\u5e8f
# \u5173\u952e\u8bcd \u2192 \u80fd\u529b\u540d\u6620\u5c04\uff0c\u8bcd\u6cd5\u547d\u4e2d\u7f6e\u4fe1\u5ea6>0.8\u65f6\u76f4\u63a5\u8fd4\u56de
# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
_FAST_LANE_MAP: dict[str, list[str]] = {
    # \u77e5\u8bc6\u5e93\u76f8\u5173
    "\u77e5\u8bc6\u5e93": ["knowledge__search"],
    "\u641c\u7d22\u77e5\u8bc6": ["knowledge__search"],
    "\u67e5\u627e\u6587\u4ef6": ["knowledge__search"],
    "\u641c\u7d22\u6587\u4ef6": ["knowledge__search"],
    "\u6709\u6ca1\u6709": ["knowledge__search"],
    "\u662f\u5426\u6709": ["knowledge__search"],
    "\u80fd\u627e\u5230": ["knowledge__search"],
    "\u5e2e\u6211\u627e": ["knowledge__search"],
    "\u67e5\u4e00\u4e0b": ["knowledge__search"],
    # \u8bb0\u5fc6\u76f8\u5173
    "\u8bb0\u5f97": ["memory__recall"],
    "\u4e4b\u524d\u8bf4": ["memory__recall"],
    "\u4e0a\u6b21": ["memory__recall"],
    # \u4e2a\u4eba\u8d44\u6599
    "\u6211\u7684\u4fe1\u606f": ["agent__get_my_profile"],
    "\u6211\u7684\u8d44\u6599": ["agent__get_my_profile"],
}


@dataclass(frozen=True)
class RankedCapability:
    capability: dict
    score: float
    lexical_score: float
    semantic_score: float
    experience_score: float = 0.0
    reference_score: float = 0.0

    def to_dict(self) -> dict:
        return {
            **self.capability,
            "retrieval_score": round(self.score, 6),
            "retrieval_diagnostics": {
                "lexical_score": round(self.lexical_score, 6),
                "semantic_score": round(self.semantic_score, 6),
                "experience_score": round(self.experience_score, 6),
                "reference_score": round(self.reference_score, 6),
            },
        }


def _tokens(value: str) -> list[str]:
    raw = [item.lower() for item in _WORD_RE.findall(value or "")]
    chinese = [item for item in raw if "\u4e00" <= item <= "\u9fff"]
    bigrams = ["".join(chinese[index:index + 2]) for index in range(max(0, len(chinese) - 1))]
    return raw + bigrams


def _search_text(capability: dict) -> str:
    retrieval = capability.get("retrieval") if isinstance(capability.get("retrieval"), dict) else {}
    parameters = capability.get("parameters") if isinstance(capability.get("parameters"), dict) else {}
    parameter_names = " ".join(str(key) for key in parameters)
    aliases = " ".join(str(item) for item in retrieval.get("aliases", []))
    return " ".join([
        str(capability.get("module") or "").replace("-", " "),
        str(capability.get("action") or "").replace("_", " "),
        str(capability.get("brief") or ""),
        str(capability.get("description") or ""),
        aliases,
        str(retrieval.get("when_to_use") or ""),
        str(retrieval.get("when_not_to_use") or ""),
        parameter_names,
    ])


def agent_visible_capabilities(capabilities: list[dict]) -> list[dict]:
    visible: list[dict] = []
    for capability in capabilities:
        retrieval = capability.get("retrieval") if isinstance(capability.get("retrieval"), dict) else {}
        if retrieval.get("expose_to_agent") is False:
            continue
        visible.append(capability)
    return visible


def normalize_json_schema(schema: object) -> object:
    """Normalize legacy module schema aliases into Draft 2020-12 JSON Schema."""
    type_aliases = {
        "int": "integer",
        "integer": "integer",
        "float": "number",
        "number": "number",
        "bool": "boolean",
        "boolean": "boolean",
        "array": "array",
        "object": "object",
        "string": "string",
        "str": "string",
        "null": "null",
    }
    if isinstance(schema, list):
        return [normalize_json_schema(item) for item in schema]
    if not isinstance(schema, dict):
        return schema

    normalized: dict[str, object] = {}
    for key, value in schema.items():
        normalized_key = str(key)
        if normalized_key == "type":
            if isinstance(value, str):
                declared = value.strip().lower()
                normalized[normalized_key] = type_aliases.get(declared, value)
                continue
            if isinstance(value, list):
                normalized[normalized_key] = [
                    type_aliases.get(item.strip().lower(), item) if isinstance(item, str) else item
                    for item in value
                ]
                continue
        normalized[normalized_key] = normalize_json_schema(value)
    return normalized


def _lexical_scores(query: str, capabilities: list[dict]) -> list[float]:
    query_tokens = _tokens(query)
    if not query_tokens:
        return [0.0] * len(capabilities)
    documents = [_tokens(_search_text(item)) for item in capabilities]
    doc_frequency: Counter[str] = Counter()
    for document in documents:
        doc_frequency.update(set(document))
    total_documents = max(1, len(documents))
    scores: list[float] = []
    for document in documents:
        counts = Counter(document)
        score = 0.0
        for token in set(query_tokens):
            frequency = counts.get(token, 0)
            if not frequency:
                continue
            inverse_document_frequency = math.log(1 + total_documents / (1 + doc_frequency[token]))
            score += (1 + math.log(frequency)) * inverse_document_frequency
        scores.append(score)
    maximum = max(scores, default=0.0)
    return [score / maximum if maximum > 0 else 0.0 for score in scores]


def _cosine(left: list[float], right: list[float]) -> float:
    if not left or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm <= 0 or right_norm <= 0:
        return 0.0
    return max(0.0, dot / (left_norm * right_norm))


def _document_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def _safe_cache_key(value: str) -> str:
    return "".join(character for character in value if character.isalnum() or character in {"-", "_"})


def _cache_path(*, user_id: int, profile_key: str, catalog_hash: str) -> Path:
    return _CACHE_DIR / f"u{int(user_id)}-{_safe_cache_key(profile_key)}-{catalog_hash}.json"


async def _embedding_profile() -> tuple[str, EmbeddingFn]:
    from app.services.model_services import (
        get_embedding_profile_contract,
        get_embeddings,
    )

    profile = get_embedding_profile_contract()
    return str(profile["profile_key"]), get_embeddings


async def _embed_in_batches(
    embedding_fn: EmbeddingFn,
    values: list[str],
    *,
    batch_size: int = 32,
) -> list[list[float]]:
    vectors: list[list[float]] = []
    for start in range(0, len(values), batch_size):
        batch = values[start:start + batch_size]
        result = await embedding_fn(batch)
        if len(result) != len(batch):
            raise RuntimeError("embedding backend returned an incomplete batch")
        vectors.extend(result)
    return vectors


async def _persistent_semantic_scores(
    *,
    user_id: int,
    query: str,
    snapshot: dict,
    capabilities: list[dict],
) -> tuple[list[float], dict]:
    if not capabilities:
        return [], {"available": False, "reason": "empty_catalog"}
    try:
        return await asyncio.wait_for(
            _persistent_semantic_scores_inner(
                user_id=user_id, query=query, snapshot=snapshot, capabilities=capabilities,
            ),
            timeout=8.0,  # 嵌入服务最多等8秒，超时走词法fallback
        )
    except asyncio.TimeoutError:
        logger.warning("Capability semantic scores timed out after 8s; using lexical fallback")
        return [0.0] * len(capabilities), {"available": False, "reason": "timeout"}
    except Exception as exc:
        logger.warning("Capability semantic index unavailable; using lexical fallback: %s", exc)
        return [0.0] * len(capabilities), {"available": False, "reason": type(exc).__name__}


async def _persistent_semantic_scores_inner(
    *,
    user_id: int,
    query: str,
    snapshot: dict,
    capabilities: list[dict],
) -> tuple[list[float], dict]:
    """实际嵌入计算逻辑，外层包超时保护。"""
    try:
        profile_key, embedding_fn = await _embedding_profile()
        path = _cache_path(
            user_id=user_id,
            profile_key=profile_key,
            catalog_hash=str(snapshot["catalog_hash"]),
        )
        cached = read_json_locked(path, {})
        if not isinstance(cached, dict):
            cached = {}
        entries = cached.get("entries") if isinstance(cached.get("entries"), dict) else {}
        documents = [_search_text(item) for item in capabilities]
        hashes = [_document_hash(value) for value in documents]
        missing_indexes = [
            index
            for index, capability in enumerate(capabilities)
            if not isinstance(entries.get(str(capability.get("capability_id"))), dict)
            or entries[str(capability.get("capability_id"))].get("document_hash") != hashes[index]
            or not isinstance(entries[str(capability.get("capability_id"))].get("vector"), list)
        ]
        if missing_indexes:
            missing_vectors = await _embed_in_batches(
                embedding_fn,
                [documents[index] for index in missing_indexes],
            )
            for index, vector in zip(missing_indexes, missing_vectors, strict=True):
                capability_id = str(capabilities[index].get("capability_id"))
                entries[capability_id] = {
                    "document_hash": hashes[index],
                    "vector": vector,
                }
            payload = {
                "version": 1,
                "user_id": int(user_id),
                "principal_version": str((snapshot.get("principal") or {}).get("profile_version") or ""),
                "catalog_hash": str(snapshot["catalog_hash"]),
                "embedding_profile": profile_key,
                "entries": entries,
            }
            update_json_locked(path, {}, lambda _current: payload)

        query_vectors = await embedding_fn([query])
        if len(query_vectors) != 1:
            raise RuntimeError("embedding backend did not return the query vector")
        scores = [
            _cosine(
                query_vectors[0],
                list((entries.get(str(capability.get("capability_id"))) or {}).get("vector") or []),
            )
            for capability in capabilities
        ]
        return scores, {
            "available": True,
            "profile_key": profile_key,
            "cache_key": path.name,
            "cache_rebuilt": bool(missing_indexes),
            "cached_document_count": len(entries),
        }
    except Exception as exc:
        logger.warning("Capability semantic index unavailable; using lexical fallback: %s", exc)
        return [0.0] * len(capabilities), {
            "available": False,
            "reason": type(exc).__name__,
        }


def _contract_hashes(capabilities: list[dict]) -> dict[str, str]:
    return {
        f"{item.get('module')}__{item.get('action')}": str(item.get("contract_hash") or "")
        for item in capabilities
        if item.get("module") and item.get("action")
    }


async def _visible_experience_patterns(
    *,
    user_id: int,
    query: str,
    capabilities: list[dict],
    conversation_id: int | None,
) -> list[dict]:
    try:
        result = await call_capability_as_system(
            "memory",
            "match_experience",
            {
                "query": query,
                "limit": 8,
                "conversation_id": conversation_id,
                "capability_contract_hashes": _contract_hashes(capabilities),
            },
            principal="system:agent-engine",
            on_behalf_of_user_id=int(user_id),
        )
        data = result.get("data") if isinstance(result, dict) else None
        return [item for item in data if isinstance(item, dict)] if isinstance(data, list) else []
    except Exception as exc:
        logger.warning("Experience pattern recall unavailable (non-fatal): %s", exc)
        return []


def _pattern_capabilities(pattern: dict) -> set[str]:
    raw = pattern.get("action_pattern", pattern.get("steps", []))
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            raw = []
    actions = raw.get("actions", []) if isinstance(raw, dict) else raw
    if not isinstance(actions, list):
        return set()
    return {
        str(item.get("capability") or item.get("tool_name") or "")
        for item in actions
        if isinstance(item, dict) and (item.get("capability") or item.get("tool_name"))
    }


def _experience_scores(capabilities: list[dict], patterns: list[dict]) -> list[float]:
    by_name: dict[str, float] = {}
    for pattern in patterns:
        similarity = max(0.0, float(pattern.get("similarity") or 0.0))
        confidence = max(0.0, min(float(pattern.get("confidence") or 0.0), 1.0))
        weight = similarity * confidence
        for name in _pattern_capabilities(pattern):
            by_name[name] = max(by_name.get(name, 0.0), weight)
    return [
        by_name.get(f"{item.get('module')}__{item.get('action')}", 0.0)
        for item in capabilities
    ]


def _reference_scores(
    capabilities: list[dict],
    *,
    available_reference_types: set[str],
    desired_reference_types: set[str],
) -> list[float]:
    scores: list[float] = []
    for capability in capabilities:
        retrieval = capability.get("retrieval") if isinstance(capability.get("retrieval"), dict) else {}
        contract = (
            capability.get("execution_contract")
            if isinstance(capability.get("execution_contract"), dict)
            else {}
        )
        input_types = {str(value) for value in retrieval.get("input_reference_types", [])}
        output_types = {str(value) for value in contract.get("output_reference_types", [])}
        input_score = 1.0 if input_types and input_types & available_reference_types else 0.0
        output_score = 1.0 if output_types and output_types & desired_reference_types else 0.0
        scores.append(max(input_score, output_score))
    return scores


def _try_fast_lane(query: str, capabilities: list[dict], snapshot: dict) -> dict | None:
    """快速通道：关键词命中高频能力直接返回，跳过全量排序和嵌入"""
    matched_names: list[str] = []
    for keyword, capability_names in _FAST_LANE_MAP.items():
        if keyword in query:
            for name in capability_names:
                if name not in matched_names:
                    matched_names.append(name)

    if not matched_names:
        return None

    # 从 capabilities 里找到对应的完整能力对象
    candidates: list[dict] = []
    for name in matched_names:
        parts = name.split("__", 1)
        if len(parts) != 2:
            continue
        module, action = parts
        for cap in capabilities:
            if cap.get("module") == module and cap.get("action") == action:
                candidates.append({
                    **cap,
                    "retrieval_score": 1.0,
                    "retrieval_diagnostics": {
                        "lexical_score": 1.0,
                        "semantic_score": 0.0,
                        "experience_score": 0.0,
                        "reference_score": 0.0,
                    },
                })
                break

    if not candidates:
        return None

    return {
        "catalog_hash": snapshot.get("catalog_hash"),
        "principal": snapshot.get("principal"),
        "query": query,
        "total_authorized": len(capabilities),
        "total_snapshot_capabilities": len(snapshot.get("capabilities") or []),
        "candidates": candidates,
        "experience_patterns": [],
        "semantic_index": {"available": False, "reason": "fast_lane_bypass"},
        "low_confidence": False,
        "strongest_retrieval_signal": 1.0,
        "retrieval_strategy": "fast_lane",
    }


def _route_ranks(values: list[float]) -> dict[int, int]:
    ordered = sorted(
        (index for index, value in enumerate(values) if value > 0),
        key=lambda index: (values[index], -index),
        reverse=True,
    )
    return {index: rank for rank, index in enumerate(ordered, start=1)}


def _rrf_scores(routes: list[tuple[float, list[float]]], count: int) -> list[float]:
    totals = [0.0] * count
    for weight, values in routes:
        for index, rank in _route_ranks(values).items():
            totals[index] += weight / (_RRF_K + rank)
    maximum = max(totals, default=0.0)
    return [value / maximum if maximum > 0 else 0.0 for value in totals]


async def retrieve_capabilities(
    *,
    user_id: int,
    query: str,
    limit: int = 8,
    embedding_fn: EmbeddingFn | None = None,
    conversation_id: int | None = None,
    available_reference_types: set[str] | None = None,
    desired_reference_types: set[str] | None = None,
) -> dict:
    t0 = time.time()
    snapshot = await _cached_capability_snapshot(user_id=user_id)
    raw_capabilities = list(snapshot.get("capabilities") or [])
    capabilities = agent_visible_capabilities(raw_capabilities)

    # ── 快速通道：关键词直接命中高频能力 ──
    fast_lane_result = _try_fast_lane(query, capabilities, snapshot)
    if fast_lane_result is not None:
        logger.info(
            "[FAST_LANE] query=%s hit=%s elapsed=%dms",
            query[:60],
            [item.get("module") + "__" + item.get("action") for item in fast_lane_result["candidates"]],
            round((time.time() - t0) * 1000),
        )
        return fast_lane_result

    # ── 常规全量排序路径 ──
    lexical = _lexical_scores(query, capabilities)
    semantic_diagnostics: dict = {"available": False, "reason": "disabled"}
    semantic = [0.0] * len(capabilities)
    if embedding_fn and capabilities:
        values = await embedding_fn([query, *[_search_text(item) for item in capabilities]])
        if len(values) == len(capabilities) + 1:
            semantic = [_cosine(values[0], value) for value in values[1:]]
            semantic_diagnostics = {"available": True, "source": "injected"}
    elif capabilities:
        semantic, semantic_diagnostics = await _persistent_semantic_scores(
            user_id=user_id,
            query=query,
            snapshot=snapshot,
            capabilities=capabilities,
        )
    experience_patterns = await _visible_experience_patterns(
        user_id=user_id,
        query=query,
        capabilities=capabilities,
        conversation_id=conversation_id,
    )
    experience = _experience_scores(capabilities, experience_patterns)
    reference = _reference_scores(
        capabilities,
        available_reference_types=available_reference_types or set(),
        desired_reference_types=desired_reference_types or set(),
    )
    fused = _rrf_scores(
        [
            (0.8, lexical),
            (1.0, semantic),
            (0.7, experience),
            (0.5, reference),
        ],
        len(capabilities),
    )
    ranked = [
        RankedCapability(
            capability=capability,
            lexical_score=lexical[index],
            semantic_score=semantic[index],
            experience_score=experience[index],
            reference_score=reference[index],
            score=fused[index],
        )
        for index, capability in enumerate(capabilities)
    ]
    ranked.sort(
        key=lambda item: (
            item.score,
            item.lexical_score,
            -int(item.capability.get("capability_id") or 0),
        ),
        reverse=True,
    )
    bounded_limit = max(1, min(int(limit or 8), 20))
    strongest_signal = max(
        (
            max(
                item.lexical_score,
                item.semantic_score,
                item.experience_score,
                item.reference_score,
            )
            for item in ranked
        ),
        default=0.0,
    )
    low_confidence = not ranked or strongest_signal < 0.15
    if low_confidence:
        bounded_limit = max(bounded_limit, min(12, len(ranked)))
    return {
        "catalog_hash": snapshot["catalog_hash"],
        "principal": snapshot["principal"],
        "query": query,
        "total_authorized": len(capabilities),
        "total_snapshot_capabilities": len(raw_capabilities),
        "candidates": [item.to_dict() for item in ranked[:bounded_limit]],
        "experience_patterns": experience_patterns,
        "semantic_index": semantic_diagnostics,
        "low_confidence": low_confidence,
        "strongest_retrieval_signal": round(strongest_signal, 6),
        "retrieval_strategy": "rrf",
    }


def direct_function_tools(candidates: list[dict]) -> list[dict]:
    tools: list[dict] = []
    for item in candidates:
        name = f"{item['module']}__{item['action']}"
        parameters = item.get("parameters") if isinstance(item.get("parameters"), dict) else {}
        schema = parameter_schema(parameters)
        tools.append({
            "type": "function",
            "function": {
                "name": name,
                "description": str(item.get("description") or item.get("brief") or name),
                "parameters": schema,
            },
        })
    return tools


def parameter_schema(parameters: dict) -> dict:
    if parameters.get("type") == "object":
        return normalize_json_schema(parameters)  # type: ignore[return-value]
    properties: dict[str, dict] = {}
    for key, value in parameters.items():
        if isinstance(value, dict):
            properties[str(key)] = normalize_json_schema(value)  # type: ignore[assignment]
            continue
        declared = str(value or "").strip().lower()
        type_name = {
            "int": "integer",
            "integer": "integer",
            "float": "number",
            "number": "number",
            "bool": "boolean",
            "boolean": "boolean",
            "array": "array",
            "object": "object",
            "string": "string",
        }.get(declared, "string")
        field_schema = {"type": type_name}
        if declared and declared not in {
            "int", "integer", "float", "number", "bool", "boolean",
            "array", "object", "string",
        }:
            field_schema["description"] = str(value)
        properties[str(key)] = field_schema
    return normalize_json_schema({"type": "object", "properties": properties})  # type: ignore[return-value]


async def validate_execution_snapshot(
    *,
    user_id: int,
    expected_catalog_hash: str,
    capability_id: int,
    capability_name: str,
) -> dict:
    """Re-run SQL pruning and reject calls planned against a stale catalog."""
    snapshot = await authorized_capability_snapshot(user_id=user_id)
    if snapshot.get("catalog_hash") != expected_catalog_hash:
        raise RuntimeError("capability_catalog_stale")
    for capability in snapshot.get("capabilities") or []:
        name = f"{capability.get('module')}__{capability.get('action')}"
        if int(capability.get("capability_id") or 0) == int(capability_id) and name == capability_name:
            return capability
    raise RuntimeError("capability_not_authorized")
