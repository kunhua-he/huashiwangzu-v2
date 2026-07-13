from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any

from app.core.exceptions import NotFound, PermissionDenied, ValidationError
from huashiwangzu_modules.memory.models import MemoryExperience
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from . import embedding_service

logger = logging.getLogger("v2.memory").getChild("experience_service")

EXPERIENCE_SIMILARITY_THRESHOLD = 0.3
EXPERIENCE_FAIL_PENALTY = 2
EXPERIENCE_MATCH_LIMIT_MAX = 20

EXPERIENCE_SCOPE_GLOBAL = "global"
EXPERIENCE_SCOPE_ORGANIZATION = "organization"
EXPERIENCE_SCOPE_DEPARTMENT = "department"
EXPERIENCE_SCOPE_POSITION = "position"
EXPERIENCE_SCOPE_USER = "user"
EXPERIENCE_SCOPE_CONVERSATION = "conversation"
# Compatibility only.  A legacy team id is treated as a department scope id;
# it is never accepted from an ordinary user caller.
EXPERIENCE_SCOPE_TEAM = "team"
EXPERIENCE_SCOPES = {
    EXPERIENCE_SCOPE_GLOBAL,
    EXPERIENCE_SCOPE_ORGANIZATION,
    EXPERIENCE_SCOPE_DEPARTMENT,
    EXPERIENCE_SCOPE_POSITION,
    EXPERIENCE_SCOPE_USER,
    EXPERIENCE_SCOPE_CONVERSATION,
}

VISIBLE_STATUSES = {"verified", "active"}
HIGH_RISK_EFFECTS = {"create", "update", "delete", "outbound", "irreversible", "write"}
SAFE_REFERENCE_TYPES = {"file", "artifact", "task", "url", "record"}

_PATH_RE = re.compile(r"(?:[A-Za-z]:\\|/Users/|/home/|/var/|/tmp/)[^\s,;，；]+")
_EMAIL_RE = re.compile(r"\b[^\s@]+@[^\s@]+\.[^\s@]+\b")
_UUID_RE = re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F-]{27,}\b")
_ID_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(?:file|owner|user|conversation|customer|client|artifact|task)[ _-]?id\s*[:=]\s*['\"]?[A-Za-z0-9_-]+['\"]?"
)
_LONG_NUMBER_RE = re.compile(r"\b\d{6,}\b")
_FILE_NAME_RE = re.compile(r"(?i)(?<![\w])[^\s/\\]{1,120}\.(?:pdf|docx?|xlsx?|pptx?|txt|md|csv|jpg|jpeg|png|gif|webp)(?![\w])")
_SENSITIVE_ENTITY_RE = re.compile(
    r"(?i)(客户|公司|项目|品牌|姓名|联系人|customer|client|company|project)\s*[:：=]?\s*[^\s,;，；]{1,80}"
)
_PERSONAL_PREFERENCE_RE = re.compile(
    r"(?i)(我的|个人|本人|偏好|习惯|默认输出|常用目录|喜欢|不喜欢|my preference|personal preference)"
)
_CAPABILITY_RE = re.compile(r"^[A-Za-z0-9_-]+?(?:__|:)[A-Za-z0-9_-]+$")


def _policy_int(name: str, default: int, minimum: int = 1) -> int:
    try:
        return max(minimum, int(os.getenv(name, str(default))))
    except ValueError:
        return default


USER_VERIFY_SUCCESSES = _policy_int("MEMORY_EXPERIENCE_USER_VERIFY_SUCCESSES", 2)
SHARED_MIN_USERS = _policy_int("MEMORY_EXPERIENCE_SHARED_MIN_USERS", 2)
GLOBAL_MIN_USERS = _policy_int("MEMORY_EXPERIENCE_GLOBAL_MIN_USERS", 3)
GLOBAL_MIN_DEPARTMENTS = _policy_int("MEMORY_EXPERIENCE_GLOBAL_MIN_DEPARTMENTS", 2)
MIN_SUCCESS_RATE = float(os.getenv("MEMORY_EXPERIENCE_MIN_SUCCESS_RATE", "0.8"))


def _is_system_caller(caller: str) -> bool:
    return bool(caller and caller.startswith("system:"))


def _parse_team_owner_ids(raw: object) -> list[int]:
    """Parse the legacy system-only team list as department ids."""
    return _coerce_positive_int_list(raw, "team_owner_ids")


def _coerce_positive_int_list(raw: object, name: str) -> list[int]:
    if raw in (None, ""):
        return []
    if not isinstance(raw, (list, tuple)):
        raise ValidationError(f"{name} must be a list")
    values: list[int] = []
    for item in raw:
        try:
            value = int(item)
        except (TypeError, ValueError) as exc:
            raise ValidationError(f"{name} must contain integers") from exc
        if value > 0 and value not in values:
            values.append(value)
    return values


def _coerce_match_limit(raw: object, default: int = 2) -> int:
    if raw in (None, ""):
        return default
    try:
        limit = int(raw)
    except (TypeError, ValueError) as exc:
        raise ValidationError("limit must be an integer") from exc
    if limit < 1 or limit > EXPERIENCE_MATCH_LIMIT_MAX:
        raise ValidationError(f"limit must be between 1 and {EXPERIENCE_MATCH_LIMIT_MAX}")
    return limit


def _coerce_bool(raw: object, name: str) -> bool:
    if not isinstance(raw, bool):
        raise ValidationError(f"{name} must be boolean")
    return raw


def _coerce_optional_positive_int(raw: object, name: str) -> int | None:
    if raw in (None, ""):
        return None
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{name} must be an integer") from exc
    if value <= 0:
        raise ValidationError(f"{name} must be positive")
    return value


def _normalize_json_text(raw: object, name: str) -> str:
    if isinstance(raw, (list, dict)):
        return json.dumps(raw, ensure_ascii=False, sort_keys=True)
    if isinstance(raw, str) and raw.strip():
        return raw
    raise ValidationError(f"{name} must be a non-empty string, list, or object")


def _normalize_optional_json_text(raw: object, name: str) -> str | None:
    if raw in (None, ""):
        return None
    return _normalize_json_text(raw, name)


def _json_value(raw: object, default: Any) -> Any:
    if raw in (None, ""):
        return default
    if isinstance(raw, (dict, list)):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return default
    return default


def _sanitize_text(value: object, limit: int = 600) -> str:
    text_value = str(value or "")
    text_value = _PATH_RE.sub("<path>", text_value)
    text_value = _EMAIL_RE.sub("<email>", text_value)
    text_value = _UUID_RE.sub("<uuid>", text_value)
    text_value = _ID_ASSIGNMENT_RE.sub("<resource_id>", text_value)
    text_value = _FILE_NAME_RE.sub("<file>", text_value)
    text_value = _LONG_NUMBER_RE.sub("<number>", text_value)
    return " ".join(text_value.split())[:limit]


def _sanitize_shared_goal(value: object) -> str:
    return _SENSITIVE_ENTITY_RE.sub(lambda match: f"{match.group(1)}:<entity>", _sanitize_text(value, 1000))


def _contains_personal_preference(goal: str, preconditions: dict) -> bool:
    if _PERSONAL_PREFERENCE_RE.search(goal):
        return True
    preference_keys = {
        "preference", "preferences", "style", "tone", "habit", "output_directory",
        "output_path", "personal", "language_preference",
    }
    return any(str(key).lower().replace("-", "_") in preference_keys for key in preconditions)


def _sanitize_mapping(value: object, *, depth: int = 0) -> object:
    if depth > 4:
        return "<truncated>"
    if isinstance(value, dict):
        result: dict[str, object] = {}
        for raw_key, raw_value in list(value.items())[:32]:
            key = str(raw_key)
            normalized = key.lower().replace("-", "_")
            if normalized == "id" or normalized.endswith("_id") or normalized in {
                "path", "locator", "display_name", "filename", "file_name", "content",
                "raw_content", "customer", "client", "user", "owner",
            }:
                result[key] = "<redacted>"
            else:
                result[key] = _sanitize_mapping(raw_value, depth=depth + 1)
        return result
    if isinstance(value, (list, tuple)):
        return [_sanitize_mapping(item, depth=depth + 1) for item in list(value)[:32]]
    if isinstance(value, str):
        return _sanitize_text(value)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return _sanitize_text(value)


def _normalize_capability_name(raw: object) -> str | None:
    value = str(raw or "").strip()
    if not _CAPABILITY_RE.fullmatch(value):
        return None
    return value.replace(":", "__", 1)


def _extract_action_pattern(steps: object, tools_used: object) -> list[dict]:
    parsed_steps = _json_value(steps, [])
    parsed_tools = _json_value(tools_used, [])
    result: list[dict] = []
    seen: set[str] = set()

    if isinstance(parsed_steps, list):
        for index, raw_step in enumerate(parsed_steps[:64]):
            if not isinstance(raw_step, dict):
                continue
            capability = None
            for key in ("capability", "tool_name", "tool", "name"):
                capability = _normalize_capability_name(raw_step.get(key))
                if capability:
                    break
            if not capability or capability in seen:
                continue
            depends_on = [
                str(item)[:64]
                for item in raw_step.get("depends_on", [])
                if isinstance(item, (str, int))
            ] if isinstance(raw_step.get("depends_on"), list) else []
            expected = [
                str(item)
                for item in raw_step.get("expected_references", [])
                if str(item) in SAFE_REFERENCE_TYPES
            ] if isinstance(raw_step.get("expected_references"), list) else []
            result.append({
                "id": str(raw_step.get("id") or f"a{index + 1}")[:64],
                "capability": capability,
                "depends_on": depends_on,
                "expected_references": expected,
            })
            seen.add(capability)

    if isinstance(parsed_tools, list):
        for raw_tool in parsed_tools[:64]:
            capability = _normalize_capability_name(raw_tool)
            if not capability or capability in seen:
                continue
            result.append({
                "id": f"a{len(result) + 1}",
                "capability": capability,
                "depends_on": [],
                "expected_references": [],
            })
            seen.add(capability)
    return result


def _capability_contract_hash(capability: dict) -> str:
    payload = {
        "module": capability.get("module"),
        "action": capability.get("action"),
        "parameters": capability.get("parameters") or {},
        "execution_contract": capability.get("execution_contract") or {},
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _snapshot_contracts(snapshot: dict | None) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for item in (snapshot or {}).get("capabilities", []):
        if not isinstance(item, dict):
            continue
        name = f"{item.get('module')}__{item.get('action')}"
        result[name] = {
            "capability_id": int(item.get("capability_id") or 0),
            "contract_hash": _capability_contract_hash(item),
            "side_effect_level": str((item.get("execution_contract") or {}).get("side_effect_level") or "none"),
        }
    return result


def _bind_pattern_contracts(
    action_pattern: list[dict],
    capability_snapshot: dict | None,
) -> tuple[list[int], dict[str, str], str, bool]:
    current = _snapshot_contracts(capability_snapshot)
    ids: list[int] = []
    hashes: dict[str, str] = {}
    risk_level = "none"
    for action in action_pattern:
        name = str(action.get("capability") or "")
        contract = current.get(name)
        if contract is None:
            raise PermissionDenied(f"经验包含当前 principal 未授权或不存在的 capability: {name}")
        capability_id = int(contract["capability_id"])
        if capability_id > 0 and capability_id not in ids:
            ids.append(capability_id)
        hashes[name] = str(contract["contract_hash"])
        if str(contract["side_effect_level"]).lower() in HIGH_RISK_EFFECTS:
            risk_level = "high"
    return sorted(ids), hashes, risk_level, bool(action_pattern and hashes)


def _principal_scope_values(
    principal_context: object | None,
    owner_id: int | None,
    conversation_id: int | None,
    legacy_department_ids: list[int] | None = None,
) -> dict[str, object]:
    return {
        "user_id": int(getattr(principal_context, "user_id", owner_id or 0) or 0),
        "organization_id": getattr(principal_context, "organization_id", None),
        "department_ids": tuple(sorted({
            *[int(item) for item in getattr(principal_context, "department_ids", ()) if int(item) > 0],
            *[int(item) for item in (legacy_department_ids or []) if int(item) > 0],
        })),
        "position_ids": tuple(sorted({
            int(item) for item in getattr(principal_context, "position_ids", ()) if int(item) > 0
        })),
        "conversation_id": conversation_id,
    }


def _normalize_scope(scope: str | None) -> str:
    normalized = str(scope or EXPERIENCE_SCOPE_USER).strip().lower()
    if normalized == EXPERIENCE_SCOPE_TEAM:
        return EXPERIENCE_SCOPE_DEPARTMENT
    if normalized not in EXPERIENCE_SCOPES:
        raise ValidationError(
            "scope_type must be global/organization/department/position/user/conversation"
        )
    return normalized


def _resolve_experience_write_scope(
    caller: str,
    caller_owner_id: int | None,
    requested_scope: str | None = None,
    requested_owner_id: int | None = None,
) -> tuple[int | None, str]:
    """Compatibility resolver for the legacy capability parameters."""
    raw_scope = str(requested_scope or "").strip().lower()
    if not raw_scope:
        raw_scope = EXPERIENCE_SCOPE_GLOBAL if _is_system_caller(caller) and not caller_owner_id else EXPERIENCE_SCOPE_USER
    scope = _normalize_scope(raw_scope)
    requested_id = _coerce_optional_positive_int(requested_owner_id, "owner_id")
    if scope == EXPERIENCE_SCOPE_GLOBAL:
        if not _is_system_caller(caller):
            raise PermissionDenied("全局经验只能由系统 curated 通路写入")
        return None, scope
    if scope in {EXPERIENCE_SCOPE_ORGANIZATION, EXPERIENCE_SCOPE_DEPARTMENT, EXPERIENCE_SCOPE_POSITION}:
        if not _is_system_caller(caller):
            raise PermissionDenied("共享经验只能由系统投影或治理通路写入")
        if not requested_id:
            raise ValidationError(f"{scope} scope requires scope_id")
        return requested_id, scope
    if scope == EXPERIENCE_SCOPE_CONVERSATION:
        if not caller_owner_id:
            raise PermissionDenied("会话经验需要用户 principal")
        return caller_owner_id, scope
    if caller_owner_id:
        return caller_owner_id, EXPERIENCE_SCOPE_USER
    if _is_system_caller(caller) and requested_id:
        return requested_id, EXPERIENCE_SCOPE_USER
    raise PermissionDenied("无法解析调用者身份")


def _scope_identity(scope_type: str, owner_id: int | None, scope_id: int | None, conversation_id: int | None) -> int | None:
    if scope_type == EXPERIENCE_SCOPE_GLOBAL:
        return None
    if scope_type == EXPERIENCE_SCOPE_USER:
        return owner_id
    if scope_type == EXPERIENCE_SCOPE_CONVERSATION:
        return scope_id or conversation_id
    return scope_id


def _status_for_pattern(exp: MemoryExperience, *, contract_bound: bool) -> tuple[str, bool]:
    success_count = int(exp.success_count or 0)
    fail_count = int(exp.failure_count or 0)
    total = success_count + fail_count
    success_rate = success_count / total if total else 0.0
    if fail_count >= 3 and success_rate < MIN_SUCCESS_RATE:
        return "suspended", False
    if exp.scope_type == EXPERIENCE_SCOPE_CONVERSATION:
        return "verified", False
    if exp.scope_type == EXPERIENCE_SCOPE_USER:
        return ("verified" if success_count >= USER_VERIFY_SUCCESSES else "candidate"), False
    if not contract_bound or exp.privacy_status != "sanitized" or success_rate < MIN_SUCCESS_RATE:
        return "candidate", False
    distinct_users = len(set(exp.contributor_user_ids or []))
    enough_users = distinct_users >= SHARED_MIN_USERS
    if exp.scope_type == EXPERIENCE_SCOPE_GLOBAL:
        enough_users = distinct_users >= GLOBAL_MIN_USERS and len(set(exp.contributor_department_ids or [])) >= GLOBAL_MIN_DEPARTMENTS
    if not enough_users:
        return "candidate", False
    if exp.risk_level == "high":
        return "review_pending", True
    return "active", False


async def _experience_to_dict(exp: MemoryExperience) -> dict:
    return {
        "id": exp.id,
        "owner_id": exp.scope_id if exp.scope_type == EXPERIENCE_SCOPE_USER else None,
        "scope": exp.scope_type,
        "scope_type": exp.scope_type,
        "scope_id": exp.scope_id,
        "trigger_condition": exp.goal_signature,
        "steps": json.dumps(exp.action_pattern or [], ensure_ascii=False, sort_keys=True),
        "tools_used": json.dumps(
            [item.get("capability") for item in (exp.action_pattern or []) if item.get("capability")],
            ensure_ascii=False,
        ),
        "goal_signature": exp.goal_signature,
        "preconditions": exp.preconditions or {},
        "action_pattern": exp.action_pattern or [],
        "completion_evidence": exp.completion_evidence or {},
        "capability_ids": exp.capability_ids or [],
        "capability_contract_hashes": exp.capability_contract_hashes or {},
        "success_weight": exp.success_count,
        "success_count": exp.success_count,
        "distinct_user_count": exp.distinct_user_count,
        "failure_count": exp.failure_count,
        "fail_count": exp.failure_count,
        "confidence": exp.confidence,
        "status": exp.status,
        "risk_level": exp.risk_level,
        "last_verified_at": exp.last_verified_at.isoformat() if exp.last_verified_at else None,
        "source_conversation_id": (
            exp.source_conversation_id
            if exp.scope_type in {EXPERIENCE_SCOPE_USER, EXPERIENCE_SCOPE_CONVERSATION}
            else None
        ),
        "active": exp.status in VISIBLE_STATUSES,
        "created_at": exp.created_at.isoformat() if exp.created_at else None,
        "updated_at": exp.updated_at.isoformat() if exp.updated_at else None,
    }


async def _find_pattern(
    db: AsyncSession,
    *,
    scope_type: str,
    scope_id: int | None,
    goal_signature: str,
    action_pattern: list[dict],
) -> MemoryExperience | None:
    scope_clause = MemoryExperience.scope_id.is_(None) if scope_id is None else MemoryExperience.scope_id == scope_id
    result = await db.execute(
        select(MemoryExperience)
        .where(
            MemoryExperience.scope_type == scope_type,
            scope_clause,
            MemoryExperience.goal_signature == goal_signature,
            MemoryExperience.action_pattern == action_pattern,
            MemoryExperience.status.notin_({"rejected", "suspended"}),
        )
        .with_for_update()
    )
    return result.scalar_one_or_none()


async def _upsert_pattern(
    db: AsyncSession,
    *,
    scope_type: str,
    scope_id: int | None,
    owner_id: int | None,
    goal_signature: str,
    goal_embedding: list[float] | None,
    preconditions: dict,
    action_pattern: list[dict],
    completion_evidence: dict,
    capability_ids: list[int],
    contract_hashes: dict[str, str],
    risk_level: str,
    source_conversation_id: int | None,
    contributor_user_id: int | None,
    contributor_department_ids: list[int],
) -> MemoryExperience:
    exp = await _find_pattern(
        db,
        scope_type=scope_type,
        scope_id=scope_id,
        goal_signature=goal_signature,
        action_pattern=action_pattern,
    )
    now = datetime.now(timezone.utc)
    if exp is None:
        user_ids = [contributor_user_id] if contributor_user_id else []
        exp = MemoryExperience(
            created_by_user_id=owner_id if scope_type in {
                EXPERIENCE_SCOPE_USER, EXPERIENCE_SCOPE_CONVERSATION,
            } else None,
            source_conversation_id=(
                source_conversation_id
                if scope_type in {EXPERIENCE_SCOPE_USER, EXPERIENCE_SCOPE_CONVERSATION}
                else None
            ),
            scope_type=scope_type,
            scope_id=scope_id,
            goal_signature=goal_signature,
            goal_embedding=goal_embedding,
            preconditions=preconditions,
            action_pattern=action_pattern,
            completion_evidence=completion_evidence,
            capability_ids=capability_ids,
            capability_contract_hashes=contract_hashes,
            success_count=1,
            distinct_user_count=len(user_ids),
            contributor_user_ids=user_ids,
            contributor_department_ids=sorted(set(contributor_department_ids)),
            confidence=1.0,
            last_verified_at=now,
            status="candidate",
            risk_level=risk_level,
            privacy_status="sanitized",
            requires_review=False,
        )
        db.add(exp)
        await db.flush()
    else:
        exp.success_count = int(exp.success_count or 0) + 1
        exp.last_verified_at = now
        if contributor_user_id:
            exp.contributor_user_ids = sorted(set(exp.contributor_user_ids or []) | {contributor_user_id})
        exp.contributor_department_ids = sorted(
            set(exp.contributor_department_ids or []) | set(contributor_department_ids)
        )
        exp.distinct_user_count = len(set(exp.contributor_user_ids or []))
        exp.capability_ids = capability_ids
        exp.capability_contract_hashes = contract_hashes
        exp.completion_evidence = completion_evidence or exp.completion_evidence
        exp.risk_level = "high" if "high" in {exp.risk_level, risk_level} else risk_level

    total = int(exp.success_count or 0) + int(exp.failure_count or 0)
    exp.confidence = round(int(exp.success_count or 0) / total, 6) if total else 0.0
    exp.distinct_user_count = len(set(exp.contributor_user_ids or []))
    status, requires_review = _status_for_pattern(exp, contract_bound=bool(contract_hashes))
    if exp.status != "active" or status == "suspended":
        exp.status = status
    exp.requires_review = requires_review
    return exp


async def _save_experience(
    db: AsyncSession,
    trigger_condition: str,
    steps: str | list | dict,
    tools_used: str | list | None = None,
    source_conversation_id: int | None = None,
    *,
    owner_id: int | None = None,
    scope: str = EXPERIENCE_SCOPE_USER,
    scope_id: int | None = None,
    principal_context: object | None = None,
    capability_snapshot: dict | None = None,
    preconditions: dict | None = None,
    completion_evidence: dict | None = None,
) -> dict:
    if not str(trigger_condition or "").strip():
        raise ValidationError("trigger_condition and steps required")
    source_conversation_id = _coerce_optional_positive_int(source_conversation_id, "source_conversation_id")
    scope_type = _normalize_scope(scope)
    resolved_scope_id = _scope_identity(scope_type, owner_id, scope_id, source_conversation_id)
    if scope_type != EXPERIENCE_SCOPE_GLOBAL and not resolved_scope_id:
        raise ValidationError(f"{scope_type} scope requires scope_id")

    goal_signature = _sanitize_text(trigger_condition, limit=1000)
    action_pattern = _extract_action_pattern(steps, tools_used)
    capability_ids, contract_hashes, risk_level, contract_bound = _bind_pattern_contracts(
        action_pattern,
        capability_snapshot,
    )
    safe_preconditions = _sanitize_mapping(preconditions or {})
    safe_completion = _sanitize_mapping(completion_evidence or {})
    if not isinstance(safe_preconditions, dict) or not isinstance(safe_completion, dict):
        raise ValidationError("preconditions and completion_evidence must be objects")
    goal_embedding = await embedding_service._compute_embedding(goal_signature)
    scopes = _principal_scope_values(principal_context, owner_id, source_conversation_id)
    contributor_user_id = int(scopes["user_id"] or 0) or owner_id
    contributor_departments = list(scopes["department_ids"])

    primary = await _upsert_pattern(
        db,
        scope_type=scope_type,
        scope_id=resolved_scope_id,
        owner_id=owner_id,
        goal_signature=goal_signature,
        goal_embedding=goal_embedding,
        preconditions=safe_preconditions,
        action_pattern=action_pattern,
        completion_evidence=safe_completion,
        capability_ids=capability_ids,
        contract_hashes=contract_hashes,
        risk_level=risk_level,
        source_conversation_id=source_conversation_id,
        contributor_user_id=contributor_user_id,
        contributor_department_ids=contributor_departments,
    )

    projection_ids: list[int] = []
    if (
        scope_type == EXPERIENCE_SCOPE_USER
        and contract_bound
        and contributor_user_id
        and not _contains_personal_preference(goal_signature, safe_preconditions)
    ):
        shared_goal_signature = _sanitize_shared_goal(goal_signature)
        projection_scopes: list[tuple[str, int | None]] = []
        organization_id = scopes["organization_id"]
        if organization_id:
            projection_scopes.append((EXPERIENCE_SCOPE_ORGANIZATION, int(organization_id)))
        projection_scopes.extend(
            (EXPERIENCE_SCOPE_DEPARTMENT, int(value)) for value in scopes["department_ids"]
        )
        projection_scopes.extend(
            (EXPERIENCE_SCOPE_POSITION, int(value)) for value in scopes["position_ids"]
        )
        if scopes["department_ids"]:
            projection_scopes.append((EXPERIENCE_SCOPE_GLOBAL, None))
        for projected_scope, projected_id in projection_scopes:
            projected = await _upsert_pattern(
                db,
                scope_type=projected_scope,
                scope_id=projected_id,
                owner_id=None,
                goal_signature=shared_goal_signature,
                goal_embedding=goal_embedding,
                preconditions=safe_preconditions,
                action_pattern=action_pattern,
                completion_evidence=safe_completion,
                capability_ids=capability_ids,
                contract_hashes=contract_hashes,
                risk_level=risk_level,
                source_conversation_id=None,
                contributor_user_id=contributor_user_id,
                contributor_department_ids=contributor_departments,
            )
            projection_ids.append(int(projected.id))

    await db.commit()
    return {
        "id": primary.id,
        "deduplicated": int(primary.success_count or 0) > 1,
        "success_weight": primary.success_count,
        "success_count": primary.success_count,
        "status": primary.status,
        "scope_type": primary.scope_type,
        "contract_bound": contract_bound,
        "projection_ids": projection_ids,
    }


def _visibility_condition(scopes: dict[str, object]):
    clauses = [
        and_(
            MemoryExperience.scope_type == EXPERIENCE_SCOPE_GLOBAL,
            MemoryExperience.scope_id.is_(None),
        )
    ]
    user_id = int(scopes.get("user_id") or 0)
    if user_id:
        clauses.append(and_(
            MemoryExperience.scope_type == EXPERIENCE_SCOPE_USER,
            MemoryExperience.scope_id == user_id,
        ))
    organization_id = scopes.get("organization_id")
    if organization_id:
        clauses.append(and_(
            MemoryExperience.scope_type == EXPERIENCE_SCOPE_ORGANIZATION,
            MemoryExperience.scope_id == int(organization_id),
        ))
    department_ids = list(scopes.get("department_ids") or [])
    if department_ids:
        clauses.append(and_(
            MemoryExperience.scope_type == EXPERIENCE_SCOPE_DEPARTMENT,
            MemoryExperience.scope_id.in_(department_ids),
        ))
    position_ids = list(scopes.get("position_ids") or [])
    if position_ids:
        clauses.append(and_(
            MemoryExperience.scope_type == EXPERIENCE_SCOPE_POSITION,
            MemoryExperience.scope_id.in_(position_ids),
        ))
    conversation_id = scopes.get("conversation_id")
    if conversation_id and user_id:
        clauses.append(and_(
            MemoryExperience.scope_type == EXPERIENCE_SCOPE_CONVERSATION,
            MemoryExperience.scope_id == int(conversation_id),
            MemoryExperience.created_by_user_id == user_id,
        ))
    return or_(*clauses)


def _contracts_current(exp: MemoryExperience, current_contracts: dict[str, dict]) -> bool:
    stored = exp.capability_contract_hashes or {}
    if not stored:
        return exp.scope_type in {EXPERIENCE_SCOPE_USER, EXPERIENCE_SCOPE_CONVERSATION}
    return all(
        name in current_contracts and current_contracts[name]["contract_hash"] == contract_hash
        for name, contract_hash in stored.items()
    )


async def _match_experience(
    db: AsyncSession,
    query: str,
    limit: int = 2,
    *,
    owner_id: int | None = None,
    team_owner_ids: list[int] | None = None,
    principal_context: object | None = None,
    capability_snapshot: dict | None = None,
    conversation_id: int | None = None,
) -> list[dict]:
    limit = _coerce_match_limit(limit)
    scopes = _principal_scope_values(
        principal_context,
        owner_id,
        conversation_id,
        legacy_department_ids=team_owner_ids,
    )
    current_contracts = _snapshot_contracts(capability_snapshot)
    authorized_ids = sorted({int(item["capability_id"]) for item in current_contracts.values() if item["capability_id"]})
    visibility = _visibility_condition(scopes)
    base = select(MemoryExperience).where(
        visibility,
        MemoryExperience.status.in_(VISIBLE_STATUSES),
        MemoryExperience.privacy_status == "sanitized",
        MemoryExperience.capability_ids.contained_by(authorized_ids),
    )
    query_vec = await embedding_service._compute_embedding(query)
    if query_vec:
        distance = MemoryExperience.goal_embedding.cosine_distance(query_vec)
        statement = base.where(
            MemoryExperience.goal_embedding.is_not(None),
            distance <= (1 - EXPERIENCE_SIMILARITY_THRESHOLD),
        ).order_by(
            distance.asc(),
            MemoryExperience.confidence.desc(),
            MemoryExperience.success_count.desc(),
        ).limit(limit * 4)
    else:
        statement = base.where(
            MemoryExperience.goal_signature.ilike(f"%{_sanitize_text(query, 160)}%")
        ).order_by(
            MemoryExperience.confidence.desc(),
            MemoryExperience.success_count.desc(),
            MemoryExperience.updated_at.desc(),
        ).limit(limit * 4)
    rows = (await db.execute(statement)).scalars().all()
    results: list[dict] = []
    scope_bonus = {
        EXPERIENCE_SCOPE_CONVERSATION: 0.05,
        EXPERIENCE_SCOPE_USER: 0.04,
        EXPERIENCE_SCOPE_POSITION: 0.03,
        EXPERIENCE_SCOPE_DEPARTMENT: 0.025,
        EXPERIENCE_SCOPE_ORGANIZATION: 0.015,
        EXPERIENCE_SCOPE_GLOBAL: 0.0,
    }
    for exp in rows:
        if not _contracts_current(exp, current_contracts):
            continue
        similarity = 0.0
        if query_vec and exp.goal_embedding is not None:
            try:
                # Ranking already used pgvector distance.  The exact score is
                # returned as a conservative threshold value for compatibility.
                similarity = EXPERIENCE_SIMILARITY_THRESHOLD
            except (TypeError, ValueError):
                similarity = 0.0
        payload = await _experience_to_dict(exp)
        payload["similarity"] = similarity
        payload["net_weight"] = int(exp.success_count or 0) - int(exp.failure_count or 0) * EXPERIENCE_FAIL_PENALTY
        payload["retrieval_score"] = round(
            (similarity * 0.55)
            + (float(exp.confidence or 0.0) * 0.4)
            + scope_bonus.get(exp.scope_type, 0.0),
            6,
        )
        results.append(payload)
    results.sort(
        key=lambda item: (
            float(item.get("retrieval_score") or 0),
            float(item.get("confidence") or 0),
            int(item.get("success_count") or 0),
        ),
        reverse=True,
    )
    return results[:limit]


async def _experience_feedback(
    db: AsyncSession,
    experience_id: int,
    success: bool,
    note: str | None = None,
    *,
    owner_id: int | None = None,
    team_owner_ids: list[int] | None = None,
    principal_context: object | None = None,
    capability_snapshot: dict | None = None,
    conversation_id: int | None = None,
) -> dict:
    experience_id = _coerce_optional_positive_int(experience_id, "experience_id")
    if experience_id is None:
        raise ValidationError("experience_id required")
    success = _coerce_bool(success, "success")
    if note is not None and not isinstance(note, str):
        raise ValidationError("note must be a string")
    scopes = _principal_scope_values(
        principal_context,
        owner_id,
        conversation_id,
        legacy_department_ids=team_owner_ids,
    )
    result = await db.execute(
        select(MemoryExperience)
        .where(MemoryExperience.id == experience_id, _visibility_condition(scopes))
        .with_for_update()
    )
    exp = result.scalar_one_or_none()
    if exp is None:
        raise NotFound("经验不存在或不在当前 principal 可见范围")
    if success:
        exp.success_count = int(exp.success_count or 0) + 1
        user_id = int(scopes["user_id"] or 0)
        if user_id:
            exp.contributor_user_ids = sorted(set(exp.contributor_user_ids or []) | {user_id})
        exp.last_verified_at = datetime.now(timezone.utc)
    else:
        exp.failure_count = int(exp.failure_count or 0) + 1
        if note:
            existing = list(exp.failure_notes or [])
            if not isinstance(existing, list):
                existing = []
            existing.append({
                "note": _sanitize_text(note, 300),
                "time": datetime.now(timezone.utc).isoformat(),
            })
            exp.failure_notes = existing[-20:]
    exp.distinct_user_count = len(set(exp.contributor_user_ids or []))
    total = int(exp.success_count or 0) + int(exp.failure_count or 0)
    exp.confidence = round(int(exp.success_count or 0) / total, 6) if total else 0.0
    current_contracts = _snapshot_contracts(capability_snapshot)
    status, requires_review = _status_for_pattern(
        exp,
        contract_bound=_contracts_current(exp, current_contracts) and bool(exp.capability_contract_hashes),
    )
    if exp.status != "active" or status == "suspended":
        exp.status = status
    exp.requires_review = requires_review
    await db.commit()
    return {
        "id": experience_id,
        "success": success,
        "success_weight": exp.success_count,
        "success_count": exp.success_count,
        "fail_count": exp.failure_count,
        "confidence": exp.confidence,
        "status": exp.status,
    }


async def _review_experience(
    db: AsyncSession,
    experience_id: int,
    decision: str,
    reviewer_id: int | None,
    note: str | None = None,
) -> dict:
    experience_id = _coerce_optional_positive_int(experience_id, "experience_id")
    if experience_id is None:
        raise ValidationError("experience_id required")
    normalized = str(decision or "").strip().lower()
    if normalized not in {"approve", "reject"}:
        raise ValidationError("decision must be approve or reject")
    result = await db.execute(
        select(MemoryExperience)
        .where(
            MemoryExperience.id == experience_id,
            MemoryExperience.status == "review_pending",
            MemoryExperience.requires_review.is_(True),
        )
        .with_for_update()
    )
    exp = result.scalar_one_or_none()
    if exp is None:
        raise NotFound("待审核经验不存在")
    if normalized == "approve":
        if exp.privacy_status != "sanitized" or not exp.capability_contract_hashes:
            raise ValidationError("经验未完成脱敏或 contract 绑定，不能发布")
        exp.status = "active"
    else:
        exp.status = "rejected"
    exp.requires_review = False
    exp.reviewed_by = reviewer_id
    exp.reviewed_at = datetime.now(timezone.utc)
    exp.review_note = _sanitize_text(note, 500) if note else None
    await db.commit()
    return {"id": exp.id, "decision": normalized, "status": exp.status}


async def _do_experience_dream(
    db: AsyncSession,
    owner_id: int | None = None,
    scope: str = EXPERIENCE_SCOPE_USER,
) -> dict:
    scope_type = _normalize_scope(scope)
    scope_id = _scope_identity(scope_type, owner_id, owner_id, None)
    clauses = [MemoryExperience.scope_type == scope_type]
    clauses.append(
        MemoryExperience.scope_id.is_(None)
        if scope_id is None
        else MemoryExperience.scope_id == scope_id
    )
    result = await db.execute(
        select(MemoryExperience).where(*clauses).with_for_update()
    )
    deactivated = 0
    for exp in result.scalars().all():
        total = int(exp.success_count or 0) + int(exp.failure_count or 0)
        confidence = int(exp.success_count or 0) / total if total else 0.0
        exp.confidence = round(confidence, 6)
        if int(exp.failure_count or 0) >= 3 and confidence < MIN_SUCCESS_RATE:
            exp.status = "suspended"
            deactivated += 1
    await db.commit()
    return {"merged": 0, "deactivated": deactivated}
