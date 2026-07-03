"""Durable agent board tools for coordinating parallel Codex agents."""

from __future__ import annotations

import fcntl
import json
import re
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

TOOL_NAMES = {
    "agent_board_claim",
    "agent_board_heartbeat",
    "agent_board_complete",
    "agent_board_block",
    "agent_board_snapshot",
}
SCHEMA_VERSION = 1
MAX_EVENTS = 800
MAX_NODE_LOG = 80
DEFAULT_STALE_AFTER_SECONDS = 1800


class BoardReadError(RuntimeError):
    """Raised when a durable board file exists but cannot be decoded."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_\-\u4e00-\u9fff]+", "-", value.strip()).strip("-")
    return cleaned[:80] or "agent-task"


def _split_values(raw: str) -> list[str]:
    return [item.strip() for item in re.split(r"[,\n]", raw or "") if item.strip()]


def board_path(repo_root: Path) -> Path:
    return repo_root / "backend" / "logs" / "agent_board.json"


def empty_board() -> dict[str, Any]:
    now = _now()
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now,
        "updated_at": now,
        "tasks": {},
        "events": [],
    }


def _normalize_board(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        return empty_board()
    board = empty_board()
    board.update(data)
    if not isinstance(board.get("tasks"), dict):
        board["tasks"] = {}
    if not isinstance(board.get("events"), list):
        board["events"] = []
    board["schema_version"] = SCHEMA_VERSION
    return board


def read_board(path: Path) -> dict[str, Any]:
    if not path.exists():
        return empty_board()
    try:
        return _normalize_board(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as exc:
        raise BoardReadError(f"Failed to read agent board {path}: {exc}") from exc


def _backup_corrupt_board(path: Path) -> Path | None:
    if not path.exists():
        return None
    backup = path.with_name(f"{path.name}.corrupt.{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}")
    path.replace(backup)
    return backup


def write_board(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data["updated_at"] = _now()
    data["events"] = list(data.get("events", []))[-MAX_EVENTS:]
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


@contextmanager
def locked_board(path: Path) -> Iterator[dict[str, Any]]:
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_name(path.name + ".lock")
    with lock_path.open("a+", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            recovered_from = None
            try:
                board = read_board(path)
            except BoardReadError:
                recovered_from = _backup_corrupt_board(path)
                board = empty_board()
                if recovered_from:
                    board["recovered_from_corrupt"] = str(recovered_from)
                    _event(
                        board,
                        action="recover_corrupt_board",
                        task_id="agent-board",
                        agent="dev_toolkit",
                        note=f"Backed up corrupt board to {recovered_from}",
                    )
            yield board
            write_board(path, board)
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _is_stale(task: dict[str, Any], stale_after_seconds: int) -> bool:
    if task.get("status") != "claimed":
        return True
    heartbeat = _parse_time(task.get("heartbeat_at") or task.get("claimed_at"))
    if heartbeat is None:
        return True
    age_seconds = (datetime.now(timezone.utc) - heartbeat).total_seconds()
    return age_seconds >= max(stale_after_seconds, 1)


def _event(
    board: dict[str, Any],
    *,
    action: str,
    task_id: str,
    agent: str,
    note: str = "",
    extra: dict[str, Any] | None = None,
) -> None:
    item: dict[str, Any] = {
        "at": _now(),
        "action": action,
        "task_id": task_id,
        "agent": agent,
    }
    if note:
        item["note"] = note
    if extra:
        item.update(extra)
    board.setdefault("events", []).append(item)


def _append_node(task: dict[str, Any], *, agent: str, action: str, note: str = "") -> None:
    if not note:
        return
    nodes = task.setdefault("node_log", [])
    if not isinstance(nodes, list):
        nodes = []
        task["node_log"] = nodes
    nodes.append({"at": _now(), "agent": agent, "action": action, "note": note})
    task["node_log"] = nodes[-MAX_NODE_LOG:]


def _task_payload(task_id: str, task: dict[str, Any]) -> dict[str, Any]:
    return {"task_id": task_id, **task}


def _task_summary(board: dict[str, Any]) -> dict[str, int]:
    summary = {"total": 0, "open": 0, "claimed": 0, "completed": 0, "blocked": 0}
    tasks = board.get("tasks", {})
    if not isinstance(tasks, dict):
        return summary
    summary["total"] = len(tasks)
    for task in tasks.values():
        status = str(task.get("status") or "open")
        summary[status] = summary.get(status, 0) + 1
    return summary


async def claim_task(
    path: Path,
    *,
    agent: str,
    task_id: str = "",
    title: str = "",
    objective: str = "",
    labels: str = "",
    node_note: str = "",
    stale_after_seconds: int = DEFAULT_STALE_AFTER_SECONDS,
    force: bool = False,
) -> str:
    if not agent.strip():
        return json.dumps({"success": False, "error": "agent is required"}, ensure_ascii=False, indent=2)
    if not task_id.strip() and not title.strip():
        return json.dumps({"success": False, "error": "task_id or title is required"}, ensure_ascii=False, indent=2)

    clean_agent = agent.strip()
    clean_task_id = _slug(task_id or title)
    now = _now()
    with locked_board(path) as board:
        tasks = board.setdefault("tasks", {})
        task = tasks.get(clean_task_id)
        created = False
        previous_owner = ""
        if not isinstance(task, dict):
            task = {
                "title": title.strip() or clean_task_id,
                "objective": objective.strip(),
                "labels": _split_values(labels),
                "created_at": now,
                "status": "open",
            }
            tasks[clean_task_id] = task
            created = True
        elif task.get("status") == "claimed" and not force and not _is_stale(task, stale_after_seconds):
            return json.dumps(
                {
                    "success": False,
                    "rejected": True,
                    "error": "task is already claimed and heartbeat is still fresh",
                    "task": _task_payload(clean_task_id, task),
                },
                ensure_ascii=False,
                indent=2,
            )
        else:
            previous_owner = str(task.get("owner_agent") or "")
            if title.strip():
                task["title"] = title.strip()
            if objective.strip():
                task["objective"] = objective.strip()
            new_labels = _split_values(labels)
            if new_labels:
                task["labels"] = sorted(set([*task.get("labels", []), *new_labels]))

        task["status"] = "claimed"
        task["owner_agent"] = clean_agent
        task["claimed_at"] = now
        task["heartbeat_at"] = now
        task["completed_at"] = None
        task["blocked_at"] = None
        task["block_reason"] = ""
        _append_node(task, agent=clean_agent, action="claim", note=node_note)
        _event(
            board,
            action="claim",
            task_id=clean_task_id,
            agent=clean_agent,
            note=node_note,
            extra={"created": created, "previous_owner": previous_owner},
        )
        payload = {
            "success": True,
            "created": created,
            "board_path": str(path),
            "task": _task_payload(clean_task_id, task),
            "summary": _task_summary(board),
        }
    return json.dumps(payload, ensure_ascii=False, indent=2)


async def heartbeat_task(path: Path, *, agent: str, task_id: str, node_note: str = "") -> str:
    clean_agent = agent.strip()
    clean_task_id = _slug(task_id)
    if not clean_agent:
        return json.dumps({"success": False, "error": "agent is required"}, ensure_ascii=False, indent=2)
    with locked_board(path) as board:
        task = board.get("tasks", {}).get(clean_task_id)
        if not isinstance(task, dict):
            return json.dumps(
                {
                    "success": False,
                    "error": "task not found",
                    "task_id": clean_task_id,
                    "hint": "Call agent_board_claim before heartbeat; heartbeat never creates tasks implicitly.",
                    "claim_example": {
                        "agent": clean_agent,
                        "task_id": clean_task_id,
                        "title": clean_task_id,
                        "node_note": node_note or "claim before heartbeat",
                    },
                },
                ensure_ascii=False,
                indent=2,
            )
        if task.get("status") != "claimed" or task.get("owner_agent") != clean_agent:
            return json.dumps(
                {
                    "success": False,
                    "rejected": True,
                    "error": "heartbeat requires the current claimed owner",
                    "task": _task_payload(clean_task_id, task),
                },
                ensure_ascii=False,
                indent=2,
            )
        task["heartbeat_at"] = _now()
        _append_node(task, agent=clean_agent, action="heartbeat", note=node_note)
        _event(board, action="heartbeat", task_id=clean_task_id, agent=clean_agent, note=node_note)
        payload = {"success": True, "board_path": str(path), "task": _task_payload(clean_task_id, task), "summary": _task_summary(board)}
    return json.dumps(payload, ensure_ascii=False, indent=2)


async def complete_task(path: Path, *, agent: str, task_id: str, result_summary: str = "", node_note: str = "") -> str:
    clean_agent = agent.strip()
    clean_task_id = _slug(task_id)
    with locked_board(path) as board:
        task = board.get("tasks", {}).get(clean_task_id)
        if not isinstance(task, dict):
            return json.dumps({"success": False, "error": "task not found", "task_id": clean_task_id}, ensure_ascii=False, indent=2)
        if task.get("owner_agent") != clean_agent:
            return json.dumps(
                {
                    "success": False,
                    "rejected": True,
                    "error": "complete requires the current task owner",
                    "task": _task_payload(clean_task_id, task),
                },
                ensure_ascii=False,
                indent=2,
            )
        task["status"] = "completed"
        task["heartbeat_at"] = _now()
        task["completed_at"] = task["heartbeat_at"]
        task["result_summary"] = result_summary.strip()
        _append_node(task, agent=clean_agent, action="complete", note=node_note or result_summary)
        _event(board, action="complete", task_id=clean_task_id, agent=clean_agent, note=node_note or result_summary)
        payload = {"success": True, "board_path": str(path), "task": _task_payload(clean_task_id, task), "summary": _task_summary(board)}
    return json.dumps(payload, ensure_ascii=False, indent=2)


async def block_task(path: Path, *, agent: str, task_id: str, reason: str, node_note: str = "") -> str:
    clean_agent = agent.strip()
    clean_task_id = _slug(task_id)
    if not reason.strip():
        return json.dumps({"success": False, "error": "reason is required"}, ensure_ascii=False, indent=2)
    with locked_board(path) as board:
        task = board.get("tasks", {}).get(clean_task_id)
        if not isinstance(task, dict):
            return json.dumps({"success": False, "error": "task not found", "task_id": clean_task_id}, ensure_ascii=False, indent=2)
        if task.get("owner_agent") != clean_agent:
            return json.dumps(
                {
                    "success": False,
                    "rejected": True,
                    "error": "block requires the current task owner",
                    "task": _task_payload(clean_task_id, task),
                },
                ensure_ascii=False,
                indent=2,
            )
        task["status"] = "blocked"
        task["heartbeat_at"] = _now()
        task["blocked_at"] = task["heartbeat_at"]
        task["block_reason"] = reason.strip()
        _append_node(task, agent=clean_agent, action="block", note=node_note or reason)
        _event(board, action="block", task_id=clean_task_id, agent=clean_agent, note=node_note or reason)
        payload = {"success": True, "board_path": str(path), "task": _task_payload(clean_task_id, task), "summary": _task_summary(board)}
    return json.dumps(payload, ensure_ascii=False, indent=2)


async def snapshot(path: Path, *, status: str = "", agent: str = "", include_events: bool = True, limit: int = 50) -> str:
    try:
        board = read_board(path)
    except BoardReadError as exc:
        return json.dumps(
            {"success": False, "error": str(exc), "board_path": str(path)},
            ensure_ascii=False,
            indent=2,
        )
    tasks = []
    for task_id, task in board.get("tasks", {}).items():
        if not isinstance(task, dict):
            continue
        if status and task.get("status") != status:
            continue
        if agent and task.get("owner_agent") != agent:
            continue
        tasks.append(_task_payload(task_id, task))
    tasks.sort(key=lambda item: str(item.get("heartbeat_at") or item.get("created_at") or ""), reverse=True)
    payload = {
        "success": True,
        "board_path": str(path),
        "summary": _task_summary(board),
        "tasks": tasks[: max(int(limit), 1)],
    }
    if include_events:
        payload["events"] = board.get("events", [])[-max(int(limit), 1):]
    return json.dumps(payload, ensure_ascii=False, indent=2)


def tool_definitions() -> list[Any]:
    from mcp.types import Tool

    common_claim_fields = {
        "agent": {"type": "string", "description": "执行 agent 标识，如 codex-conductor-r5 / knowledge-live-chain-r4"},
        "task_id": {"type": "string", "description": "稳定任务 id；为空时由 title 生成", "default": ""},
        "title": {"type": "string", "description": "任务标题；task_id 为空时必填", "default": ""},
        "objective": {"type": "string", "description": "任务目标/范围", "default": ""},
        "labels": {"type": "string", "description": "逗号或换行分隔标签", "default": ""},
        "node_note": {"type": "string", "description": "本节点进度说明，会写入 node_log", "default": ""},
        "stale_after_seconds": {"type": "number", "description": "心跳超过该秒数视为 stale 可被重新 claim", "default": DEFAULT_STALE_AFTER_SECONDS},
        "force": {"type": "boolean", "description": "是否强制接管已 claim 任务", "default": False},
    }
    task_owner_fields = {
        "agent": {"type": "string", "description": "当前任务 owner agent"},
        "task_id": {"type": "string", "description": "任务 id"},
        "node_note": {"type": "string", "description": "本节点进度说明，会写入 node_log", "default": ""},
    }
    return [
        Tool(
            name="agent_board_claim",
            description="Durable agent board: 创建或认领一个本地持久化任务；新任务写入 backend/logs/agent_board.json，已有活跃 owner 未 stale 时拒绝。",
            inputSchema={"type": "object", "properties": common_claim_fields, "required": ["agent"]},
        ),
        Tool(
            name="agent_board_heartbeat",
            description="Durable agent board: 当前 owner 刷新任务心跳并追加节点进度，避免多子代理进度丢失。",
            inputSchema={"type": "object", "properties": task_owner_fields, "required": ["agent", "task_id"]},
        ),
        Tool(
            name="agent_board_complete",
            description="Durable agent board: 当前 owner 将任务标记 completed，并记录结果摘要。",
            inputSchema={
                "type": "object",
                "properties": {
                    **task_owner_fields,
                    "result_summary": {"type": "string", "description": "完成结果摘要", "default": ""},
                },
                "required": ["agent", "task_id"],
            },
        ),
        Tool(
            name="agent_board_block",
            description="Durable agent board: 当前 owner 将任务标记 blocked，并记录稳定卡点原因。",
            inputSchema={
                "type": "object",
                "properties": {
                    **task_owner_fields,
                    "reason": {"type": "string", "description": "卡点原因，必填"},
                },
                "required": ["agent", "task_id", "reason"],
            },
        ),
        Tool(
            name="agent_board_snapshot",
            description="Durable agent board: 查看持久化任务板，可按 status/agent 过滤，附最近事件。",
            inputSchema={
                "type": "object",
                "properties": {
                    "status": {"type": "string", "description": "可选状态过滤: open/claimed/completed/blocked", "default": ""},
                    "agent": {"type": "string", "description": "可选 owner agent 过滤", "default": ""},
                    "include_events": {"type": "boolean", "description": "是否返回最近事件", "default": True},
                    "limit": {"type": "number", "description": "返回任务/事件数量上限", "default": 50},
                },
            },
        ),
    ]


def handles_tool(name: str) -> bool:
    return name in TOOL_NAMES


async def handle_tool(repo_root: Path, name: str, arguments: dict[str, Any]) -> str:
    path = board_path(repo_root)
    if name == "agent_board_claim":
        return await claim_task(
            path,
            agent=arguments.get("agent", ""),
            task_id=arguments.get("task_id", ""),
            title=arguments.get("title", ""),
            objective=arguments.get("objective", ""),
            labels=arguments.get("labels", ""),
            node_note=arguments.get("node_note", ""),
            stale_after_seconds=int(arguments.get("stale_after_seconds", DEFAULT_STALE_AFTER_SECONDS)),
            force=bool(arguments.get("force", False)),
        )
    if name == "agent_board_heartbeat":
        return await heartbeat_task(
            path,
            agent=arguments.get("agent", ""),
            task_id=arguments.get("task_id", ""),
            node_note=arguments.get("node_note", ""),
        )
    if name == "agent_board_complete":
        return await complete_task(
            path,
            agent=arguments.get("agent", ""),
            task_id=arguments.get("task_id", ""),
            result_summary=arguments.get("result_summary", ""),
            node_note=arguments.get("node_note", ""),
        )
    if name == "agent_board_block":
        return await block_task(
            path,
            agent=arguments.get("agent", ""),
            task_id=arguments.get("task_id", ""),
            reason=arguments.get("reason", ""),
            node_note=arguments.get("node_note", ""),
        )
    if name == "agent_board_snapshot":
        return await snapshot(
            path,
            status=arguments.get("status", ""),
            agent=arguments.get("agent", ""),
            include_events=bool(arguments.get("include_events", True)),
            limit=int(arguments.get("limit", 50)),
        )
    raise ValueError(f"未知 agent board 工具: {name}")
