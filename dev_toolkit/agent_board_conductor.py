"""Conductor summary helpers for agent board snapshots."""

from __future__ import annotations

import re
import shlex
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _heartbeat_age_seconds(task: dict[str, Any]) -> int | None:
    heartbeat = _parse_time(task.get("heartbeat_at") or task.get("claimed_at") or task.get("created_at"))
    if heartbeat is None:
        return None
    return max(int((datetime.now(timezone.utc) - heartbeat).total_seconds()), 0)


def _latest_note(task: dict[str, Any]) -> str:
    nodes = task.get("node_log")
    if isinstance(nodes, list) and nodes:
        latest = nodes[-1]
        if isinstance(latest, dict):
            return str(latest.get("note") or "")
    return ""


def _recent_memory_links(repo_root: Path, *, limit: int = 8) -> list[dict[str, str]]:
    memory_dir = repo_root / "开发文档" / "项目记忆"
    if not memory_dir.exists():
        return []
    memories: list[dict[str, str]] = []
    for path in sorted(memory_dir.glob("*.md"), key=lambda item: item.stat().st_mtime, reverse=True):
        if path.stem.startswith("_"):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")[:2000]
        meta = dict(re.findall(r'^(name|agent|created):\s*"?([^"\n]+)"?', text, re.MULTILINE))
        memories.append({
            "name": meta.get("name", path.stem),
            "agent": meta.get("agent", ""),
            "created": meta.get("created", ""),
            "path": str(path.relative_to(repo_root)),
        })
        if len(memories) >= max(limit, 1):
            break
    return memories


def _git_stage_plan(repo_root: Path) -> dict[str, Any]:
    completed = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
        timeout=10,
    )
    files = [line[3:] for line in completed.stdout.splitlines() if len(line) > 3]
    grouped: dict[str, list[str]] = {}
    for path in files:
        grouped.setdefault(path.split("/", 1)[0], []).append(path)
    return {
        "dirty_count": len(files),
        "files": files,
        "grouped_pathspecs": grouped,
        "suggested_git_add": [
            f"git add -- {' '.join(shlex.quote(path) for path in paths)}"
            for paths in grouped.values()
        ],
    }


def build_conductor_summary(
    repo_root: Path,
    tasks: list[dict[str, Any]],
    *,
    stale_after_seconds: int,
    memory_limit: int,
) -> dict[str, Any]:
    lanes: dict[str, dict[str, Any]] = {}
    stale_tasks: list[dict[str, Any]] = []
    for task in tasks:
        status = str(task.get("status") or "open")
        lane = lanes.setdefault(status, {"count": 0, "tasks": []})
        age = _heartbeat_age_seconds(task)
        stale = status == "claimed" and (age is None or age >= max(stale_after_seconds, 1))
        item = {
            "task_id": task.get("task_id", ""),
            "title": task.get("title", ""),
            "owner_agent": task.get("owner_agent", ""),
            "heartbeat_age_seconds": age,
            "stale": stale,
            "latest_note": _latest_note(task),
            "result_summary": task.get("result_summary", ""),
            "block_reason": task.get("block_reason", ""),
        }
        lane["count"] += 1
        lane["tasks"].append(item)
        if stale:
            stale_tasks.append(item)
    return {
        "lanes": lanes,
        "stale_after_seconds": max(stale_after_seconds, 1),
        "stale_tasks": stale_tasks,
        "recent_memory_links": _recent_memory_links(repo_root, limit=memory_limit),
        "stage_plan": _git_stage_plan(repo_root),
    }
