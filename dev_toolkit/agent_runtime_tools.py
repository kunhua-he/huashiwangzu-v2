"""Read-only Agent conversation and tool-runtime diagnostics for the toolkit."""

from __future__ import annotations

import asyncio
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any

TOOL_NAMES = {"agent_runtime_snapshot"}
_DEFAULT_DAYS = 30
_MAX_DAYS = 365
_DEFAULT_SAMPLE_LIMIT = 12
_MAX_SAMPLE_LIMIT = 50


def tool_definitions() -> list[Any]:
    from mcp.types import Tool

    return [
        Tool(
            name="agent_runtime_snapshot",
            description=(
                "只读分析 Agent 对话、工具调用和失败记录，按影响排序输出流程瓶颈、"
                "证据数量和建议修复位置。"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "owner_id": {
                        "type": "integer",
                        "description": "可选用户 ID；传入后对话和轨迹只统计该用户。",
                    },
                    "days": {
                        "type": "integer",
                        "description": "统计最近多少天，默认30，最大365。",
                        "default": _DEFAULT_DAYS,
                    },
                    "sample_limit": {
                        "type": "integer",
                        "description": "返回多少条已截断的代表性用户请求，默认12，最大50。",
                        "default": _DEFAULT_SAMPLE_LIMIT,
                    },
                },
            },
        ),
    ]


def handles_tool(name: str) -> bool:
    return name in TOOL_NAMES


async def handle_tool(repo_root: Path, name: str, arguments: dict[str, Any]) -> str:
    if name != "agent_runtime_snapshot":
        raise ValueError(f"未知 Agent 运行态工具: {name}")
    owner_id = _optional_positive_int(arguments.get("owner_id"))
    days = _bounded_int(arguments.get("days"), default=_DEFAULT_DAYS, maximum=_MAX_DAYS)
    sample_limit = _bounded_int(
        arguments.get("sample_limit"),
        default=_DEFAULT_SAMPLE_LIMIT,
        maximum=_MAX_SAMPLE_LIMIT,
    )
    snapshot = await _db_snapshot(
        repo_root,
        owner_id=owner_id,
        days=days,
        sample_limit=sample_limit,
    )
    return json.dumps(snapshot, ensure_ascii=False, indent=2, default=str)


async def _db_snapshot(
    repo_root: Path,
    *,
    owner_id: int | None,
    days: int,
    sample_limit: int,
) -> dict[str, Any]:
    script = """
import asyncio
import json
from sqlalchemy import text
from app.database import AsyncSessionLocal

OWNER_ID = OWNER_ID_VALUE
DAYS = DAYS_VALUE
SAMPLE_LIMIT = SAMPLE_LIMIT_VALUE

async def query(db, statement, params=None):
    return [dict(row) for row in (await db.execute(text(statement), params or {})).mappings().all()]

async def main():
    params = {"owner_id": OWNER_ID, "days": DAYS, "sample_limit": SAMPLE_LIMIT}
    async with AsyncSessionLocal() as db:
        conversations = await query(db, '''
            SELECT c.id, c.owner_id, c.title, c.status, c.processing, c.updated_at,
                   count(m.id) FILTER (WHERE m.role = 'user') AS user_messages,
                   count(m.id) FILTER (WHERE m.role = 'assistant') AS assistant_messages
            FROM agent_conversations c
            LEFT JOIN agent_messages m ON m.conversation_id = c.id AND m.status = 'active'
            WHERE (CAST(:owner_id AS integer) IS NULL OR c.owner_id = CAST(:owner_id AS integer))
              AND c.updated_at >= now() - make_interval(days => :days)
            GROUP BY c.id
            ORDER BY c.updated_at DESC
        ''', params)
        samples = await query(db, '''
            SELECT t.id, t.conversation_id, t.owner_id, t.created_at,
                   left(t.user_input, 320) AS user_input,
                   t.error_occurred, t.tool_calls, t.tool_results
            FROM agent_trajectory_records t
            WHERE (CAST(:owner_id AS integer) IS NULL OR t.owner_id = CAST(:owner_id AS integer))
              AND t.created_at >= now() - make_interval(days => :days)
            ORDER BY t.id DESC
            LIMIT :sample_limit
        ''', params)
        all_trajectories = await query(db, '''
            SELECT t.owner_id, t.error_occurred, t.tool_calls, t.tool_results
            FROM agent_trajectory_records t
            WHERE (CAST(:owner_id AS integer) IS NULL OR t.owner_id = CAST(:owner_id AS integer))
              AND t.created_at >= now() - make_interval(days => :days)
            ORDER BY t.id DESC
            LIMIT 500
        ''', params)
        failures = await query(db, '''
            SELECT COALESCE(tool_name, '') AS tool_name,
                   COALESCE(target_module, '') AS target_module,
                   COALESCE(action, '') AS action,
                   COALESCE(error_class, '') AS error_class,
                   COALESCE(error_signature, '') AS error_signature,
                   count(*) AS count,
                   max(created_at) AS last_seen
            FROM agent_tool_calls
            WHERE created_at >= now() - make_interval(days => :days)
              AND (status NOT IN ('completed', 'success', 'succeeded') OR error_class IS NOT NULL)
            GROUP BY tool_name, target_module, action, error_class, error_signature
            ORDER BY count(*) DESC, last_seen DESC
            LIMIT 50
        ''', params)
        checkpoints = await query(db, '''
            SELECT DISTINCT ON (c.conversation_id)
                   c.conversation_id, c.owner_id, c.checkpoint_id,
                   c.checkpoint_type, c.created_at, c.channel_values
            FROM agent_checkpoints c
            WHERE (CAST(:owner_id AS integer) IS NULL OR c.owner_id = CAST(:owner_id AS integer))
              AND c.created_at >= now() - make_interval(days => :days)
            ORDER BY c.conversation_id, c.step DESC, c.id DESC
            LIMIT 500
        ''', params)
    print(json.dumps({
        "conversations": conversations,
        "samples": samples,
        "trajectories": all_trajectories,
        "failure_groups": failures,
        "checkpoints": checkpoints,
    }, ensure_ascii=False, default=str))

asyncio.run(main())
""".replace("OWNER_ID_VALUE", repr(owner_id)).replace("DAYS_VALUE", str(days)).replace("SAMPLE_LIMIT_VALUE", str(sample_limit))
    env = os.environ.copy()
    env["PYTHONPATH"] = "backend"
    process = await asyncio.create_subprocess_exec(
        _project_python(repo_root),
        "-c",
        script,
        cwd=repo_root,
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        return {
            "success": False,
            "error": stderr.decode("utf-8", errors="replace")[-4000:],
        }
    raw = json.loads(stdout.decode("utf-8"))
    # agent_tool_calls does not carry owner_id for regular chat turns. For an
    # owner-scoped diagnosis, trajectories are the authoritative source.
    if owner_id is not None:
        raw["failure_groups"] = []
    return _summarize_snapshot(
        raw,
        owner_id=owner_id,
        days=days,
        sample_limit=sample_limit,
    )


def _summarize_snapshot(
    raw: dict[str, Any],
    *,
    owner_id: int | None,
    days: int,
    sample_limit: int,
) -> dict[str, Any]:
    trajectories = [item for item in raw.get("trajectories", []) if isinstance(item, dict)]
    tool_counts: Counter[str] = Counter()
    result_errors: Counter[tuple[str, str]] = Counter()
    meta_calls = 0
    capability_calls = 0
    errored_turns = 0
    for trajectory in trajectories:
        if trajectory.get("error_occurred"):
            errored_turns += 1
        for call in _as_list(trajectory.get("tool_calls")):
            name = _tool_name(call)
            if not name:
                continue
            tool_counts[name] += 1
            if name in {"skill_list", "skill_describe", "skill_use"}:
                meta_calls += 1
            else:
                capability_calls += 1
        for result in _as_list(trajectory.get("tool_results")):
            error = _result_error(result)
            if error:
                result_errors[(_tool_name(result) or "unknown", error)] += 1

    failure_groups = [item for item in raw.get("failure_groups", []) if isinstance(item, dict)]
    for (tool_name, error), count in result_errors.items():
        failure_groups.append({
            "tool_name": tool_name,
            "error_signature": error,
            "count": count,
        })
    issues = _build_issues(
        meta_calls=meta_calls,
        capability_calls=capability_calls,
        tool_counts=tool_counts,
        result_errors=result_errors,
        failure_groups=failure_groups,
    )
    checkpoint_health = _checkpoint_health(
        [item for item in raw.get("checkpoints", []) if isinstance(item, dict)],
    )
    issues.extend(checkpoint_health.pop("issues"))
    issues = _dedupe_issues(issues)
    conversations = [item for item in raw.get("conversations", []) if isinstance(item, dict)]
    return {
        "success": True,
        "scope": {
            "owner_id": owner_id,
            "days": days,
            "trajectory_limit": 500,
            "sample_limit": sample_limit,
            "tool_call_ledger_scope": "global_recent_window" if owner_id is None else "trajectory_only_for_owner",
        },
        "summary": {
            "conversation_count": len(conversations),
            "trajectory_count": len(trajectories),
            "errored_trajectory_count": errored_turns,
            "meta_tool_calls": meta_calls,
            "capability_calls": capability_calls,
            "meta_tool_call_ratio": round(meta_calls / max(1, meta_calls + capability_calls), 3),
            "failure_group_count": len(failure_groups),
            "checkpoint_count": checkpoint_health["checkpoint_count"],
            "action_plan_checkpoint_count": checkpoint_health["action_plan_checkpoint_count"],
        },
        "checkpoint_health": checkpoint_health,
        "top_tools": [
            {"tool_name": name, "calls": count}
            for name, count in tool_counts.most_common(20)
        ],
        "top_result_errors": [
            {"tool_name": name, "error": error, "count": count}
            for (name, error), count in result_errors.most_common(20)
        ],
        "failure_groups": failure_groups,
        "issues": issues,
        "sample_requests": [_sample_view(item) for item in raw.get("samples", []) if isinstance(item, dict)],
    }


def _build_issues(
    *,
    meta_calls: int,
    capability_calls: int,
    tool_counts: Counter[str],
    result_errors: Counter[tuple[str, str]],
    failure_groups: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    total_calls = meta_calls + capability_calls
    if total_calls >= 8 and meta_calls / max(1, total_calls) >= 0.45:
        issues.append({
            "key": "tool_discovery_overhead",
            "severity": "high",
            "evidence_count": meta_calls,
            "summary": "元工具调用占比过高，Agent 花太多轮在找工具。",
            "recommended_fix": "检查授权 capability 快照、Top-K 召回与 structured planner；正常请求不应调用三元元工具。",
            "code_areas": [
                "modules/agent/backend/services/capability_catalog.py",
                "modules/agent/backend/runtime/action_planner.py",
            ],
        })
    for group in failure_groups:
        signature = str(group.get("error_signature") or "")
        count = int(group.get("count") or 0)
        tool_name = str(group.get("tool_name") or "")
        if "Unsupported file extension" in signature:
            issues.append(_issue(
                "image_routed_to_text_reader", count,
                "图片被路由到文本读取工具。",
                "检查 capability 的输入 ResourceRef 类型与 Planner 引用绑定，禁止按业务名称硬编码分流。",
                ["modules/agent/backend/runtime/action_plan_validator.py", "modules/agent/backend/services/capability_catalog.py"],
            ))
        elif "must be a positive integer" in signature or "cannot be interpreted as an integer" in signature:
            issues.append(_issue(
                "file_identifier_contract_mismatch", count,
                "模型传递的文件 ID 类型或字段名不符合契约。",
                "检查 Planner schema、ResourceRef 引用绑定和 capability input_schema，失败后显式重新规划。",
                ["modules/agent/backend/runtime/action_planner.py", "modules/agent/backend/runtime/action_plan_validator.py"],
            ))
        elif "Skill not found" in signature:
            issues.append(_issue(
                "capability_discovery_drift", count,
                "技能发现结果和后续 describe/use 的可用能力不一致。",
                "检查 catalog_hash、permission_version 与执行前 SQL 再授权；快照变化必须重新规划。",
                ["modules/agent/backend/services/capability_catalog.py", "backend/app/services/module_registry.py"],
            ))
        elif "在 18 秒内没有返回" in signature:
            issues.append(_issue(
                "knowledge_search_timeout", count,
                "知识库检索被通用快速工具超时中断。",
                "为知识库检索设置独立超时和候选结果降级，不以 18 秒硬中断作为最终失败。",
                ["modules/agent/backend/runtime/runtime_policy.py", "modules/agent/backend/runtime/tool_loop_runtime.py"],
            ))
        elif "Requires at least" in signature:
            issues.append(_issue(
                "role_preflight_missing", count,
                f"{tool_name or '工具'} 在执行后才暴露角色不足。",
                "核对 SQL capability policy 和执行前再授权，未授权 schema 不得进入模型上下文。",
                ["backend/app/services/permission_service.py", "backend/app/services/module_registry.py"],
            ))
    for (tool_name, error), count in result_errors.items():
        if "File not found" in error:
            issues.append(_issue(
                "stale_file_reference", count,
                "文件记录存在但磁盘源不可用。",
                "返回明确的源文件不可用状态，并触发文件/知识库生命周期治理，不重复调用解析器。",
                ["modules/desktop-tools/backend/router.py"],
            ))
    return _dedupe_issues(issues)


def _dedupe_issues(issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: dict[str, dict[str, Any]] = {}
    for issue in issues:
        existing = deduped.get(issue["key"])
        if existing is None:
            deduped[issue["key"]] = issue
        else:
            existing["evidence_count"] += int(issue["evidence_count"])
    return sorted(deduped.values(), key=lambda item: (-int(item["evidence_count"]), item["key"]))


def _checkpoint_health(checkpoints: list[dict[str, Any]]) -> dict[str, Any]:
    action_plan_count = 0
    stale_snapshot_count = 0
    permission_leakage_count = 0
    incomplete_reference_count = 0
    interrupted_running_count = 0
    for row in checkpoints:
        channel = row.get("channel_values")
        if not isinstance(channel, dict):
            continue
        catalog = channel.get("capability_catalog")
        plan_checkpoint = channel.get("action_plan_checkpoint")
        if not isinstance(plan_checkpoint, dict) or not plan_checkpoint:
            continue
        action_plan_count += 1
        plan = plan_checkpoint.get("plan") if isinstance(plan_checkpoint.get("plan"), dict) else {}
        if isinstance(catalog, dict) and (
            plan.get("catalog_hash")
            and plan.get("catalog_hash") != catalog.get("catalog_hash")
        ):
            stale_snapshot_count += 1
        principal = catalog.get("principal") if isinstance(catalog, dict) else {}
        principal_user_id = principal.get("user_id") if isinstance(principal, dict) else None
        if principal_user_id is not None and int(principal_user_id) != int(row.get("owner_id") or 0):
            permission_leakage_count += 1
        observations = plan_checkpoint.get("observations")
        if not isinstance(observations, dict):
            continue
        for observation in observations.values():
            if not isinstance(observation, dict):
                continue
            if observation.get("state") == "running":
                interrupted_running_count += 1
            if observation.get("state") != "completed":
                continue
            for reference in observation.get("references") or []:
                if not isinstance(reference, dict) or not reference.get("type") or reference.get("id") in (None, ""):
                    incomplete_reference_count += 1
    issues: list[dict[str, Any]] = []
    checks = (
        ("stale_snapshot", stale_snapshot_count, "checkpoint 中计划与能力目录 hash 不一致。", "核对 snapshot 失效与显式 replan 路径。"),
        ("permission_leakage", permission_leakage_count, "checkpoint 的 principal 与 owner 不一致，存在权限上下文串用风险。", "立即检查 SQL principal 裁剪和 checkpoint owner 绑定。"),
        ("resource_ref_incomplete", incomplete_reference_count, "已完成动作包含不完整 ResourceRef。", "补齐 capability output contract，并禁止按字段名猜引用。"),
        ("checkpoint_recovery_pending", interrupted_running_count, "最新 checkpoint 仍有 running 动作等待恢复判定。", "按幂等账本收敛或阻塞副作用动作，禁止盲目重发。"),
    )
    for key, count, summary, fix in checks:
        if count:
            issues.append(_issue(
                key,
                count,
                summary,
                fix,
                ["modules/agent/backend/runtime/tool_loop_runtime.py", "modules/agent/backend/runtime/action_graph_executor.py"],
            ))
    return {
        "checkpoint_count": len(checkpoints),
        "action_plan_checkpoint_count": action_plan_count,
        "stale_snapshot_count": stale_snapshot_count,
        "permission_leakage_count": permission_leakage_count,
        "incomplete_reference_count": incomplete_reference_count,
        "interrupted_running_count": interrupted_running_count,
        "issues": issues,
    }


def _issue(key: str, evidence_count: int, summary: str, recommended_fix: str, code_areas: list[str]) -> dict[str, Any]:
    return {
        "key": key,
        "severity": "high" if evidence_count >= 3 else "medium",
        "evidence_count": evidence_count,
        "summary": summary,
        "recommended_fix": recommended_fix,
        "code_areas": code_areas,
    }


def _tool_name(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    function = value.get("function")
    if isinstance(function, dict):
        return str(function.get("name") or "")
    return str(value.get("effective_tool_name") or value.get("name") or value.get("tool_name") or "")


def _result_error(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    result = value.get("result") or value.get("summary") or value
    if not isinstance(result, dict):
        return ""
    error = result.get("error") or result.get("error_message")
    return str(error or "")[:320]


def _sample_view(value: dict[str, Any]) -> dict[str, Any]:
    return {
        "trajectory_id": value.get("id"),
        "conversation_id": value.get("conversation_id"),
        "owner_id": value.get("owner_id"),
        "created_at": value.get("created_at"),
        "user_input": value.get("user_input"),
        "error_occurred": bool(value.get("error_occurred")),
        "tools": [_tool_name(item) for item in _as_list(value.get("tool_calls")) if _tool_name(item)],
    }


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _optional_positive_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _bounded_int(value: Any, *, default: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(1, min(parsed, maximum))


def _project_python(repo_root: Path) -> str:
    candidate = repo_root / "backend" / ".venv" / "bin" / "python"
    return str(candidate) if candidate.exists() else "python3"
