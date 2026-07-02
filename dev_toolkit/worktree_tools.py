"""Git worktree boundary tools for the project toolkit MCP server."""

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

TOOL_NAMES = {"worktree_guard"}


async def git_status_summary(run_command_json, repo_root: Path) -> dict[str, Any]:
    result = await run_command_json(
        ["git", "status", "--short", "--branch"],
        cwd=repo_root,
        timeout=10,
    )
    lines = [line for line in result.get("stdout", "").splitlines() if line.strip()]
    branch = lines[0].removeprefix("## ") if lines else ""
    changed = lines[1:]
    return {
        "branch": branch,
        "is_main": branch.split("...")[0] in {"main", "master"},
        "dirty_count": len(changed),
        "sample": changed[:25],
    }


async def git_changed_entries(run_command_json, repo_root: Path, include_untracked: bool = True) -> list[dict[str, str]]:
    cmd = ["git", "-c", "core.quotePath=false", "status", "--porcelain=v1"]
    if include_untracked:
        cmd.append("--untracked-files=all")
    result = await run_command_json(cmd, cwd=repo_root, timeout=10)
    entries: list[dict[str, str]] = []
    for line in result.get("stdout", "").splitlines():
        if not line.strip():
            continue
        status = line[:2]
        path = line[3:].strip()
        if " -> " in path:
            path = path.rsplit(" -> ", 1)[1]
        entries.append({"status": status, "path": path})
    return entries


def split_prefixes(raw: str) -> list[str]:
    return [item.strip().strip("/") for item in re.split(r"[,\n]", raw or "") if item.strip()]


def path_matches_prefix(path: str, prefix: str) -> bool:
    normalized = prefix.strip().strip("/")
    if not normalized:
        return False
    return path == normalized or path.startswith(normalized + "/")


def default_forbidden_prefixes() -> list[str]:
    return [
        ".git",
        "frontend/node_modules",
        "backend/.venv",
        "backend/venv",
        "__pycache__",
        "后端",
        "脚本",
        "部署",
        "backend/_废弃",
        "backend/脚本",
    ]


def group_changed_path(path: str) -> str:
    parts = path.split("/")
    if not parts:
        return "(unknown)"
    if parts[0] == "modules" and len(parts) > 1:
        return f"modules/{parts[1]}"
    if parts[0] in {"backend", "frontend", "dev_toolkit", "scripts", "开发文档"}:
        return "/".join(parts[:2]) if len(parts) > 1 else parts[0]
    return parts[0]


async def worktree_guard(
    run_command_json,
    repo_root: Path,
    module_key: str = "",
    allowed_prefixes: str = "",
    forbidden_prefixes: str = "",
    include_untracked: bool = True,
) -> str:
    """Guard dirty worktree boundaries, including untracked files."""
    entries = await git_changed_entries(run_command_json, repo_root, include_untracked=include_untracked)
    paths = sorted({entry["path"] for entry in entries})
    allowed = split_prefixes(allowed_prefixes)
    if module_key and not allowed:
        allowed = [f"modules/{module_key}"]
    forbidden = default_forbidden_prefixes() + split_prefixes(forbidden_prefixes)

    outside_allowed = [
        path for path in paths
        if allowed and not any(path_matches_prefix(path, prefix) for prefix in allowed)
    ]
    forbidden_hits = [
        path for path in paths
        if any(path_matches_prefix(path, prefix) for prefix in forbidden)
    ]

    by_group = Counter(group_changed_path(path) for path in paths)
    payload = {
        "success": not outside_allowed and not forbidden_hits,
        "module_key": module_key,
        "allowed_prefixes": allowed,
        "forbidden_prefixes": forbidden,
        "include_untracked": include_untracked,
        "changed_count": len(paths),
        "changed_files": paths[:200],
        "changed_by_group": dict(sorted(by_group.items())),
        "outside_allowed_count": len(outside_allowed),
        "outside_allowed": outside_allowed[:100],
        "forbidden_hit_count": len(forbidden_hits),
        "forbidden_hits": forbidden_hits[:100],
        "hint": (
            "模块任务建议传 module_key；框架/全局任务可传 allowed_prefixes。"
            "本工具会包含 untracked 文件，比 git diff --name-only 更适合验收边界。"
        ),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def tool_definitions() -> list[Any]:
    from mcp.types import Tool

    return [
        Tool(
            name="worktree_guard",
            description="开工/收工边界守卫：汇总 dirty 文件(含 untracked)，按组归类，并校验 module_key/allowed_prefixes/forbidden_prefixes。",
            inputSchema={
                "type": "object",
                "properties": {
                    "module_key": {"type": "string", "description": "模块 key；传入后默认只允许 modules/{module_key}/", "default": ""},
                    "allowed_prefixes": {"type": "string", "description": "逗号或换行分隔的允许路径前缀；为空则只做 forbidden 检查", "default": ""},
                    "forbidden_prefixes": {"type": "string", "description": "额外禁止路径前缀，逗号或换行分隔", "default": ""},
                    "include_untracked": {"type": "boolean", "description": "是否包含未跟踪文件", "default": True},
                },
            },
        ),
    ]


def handles_tool(name: str) -> bool:
    return name in TOOL_NAMES


async def handle_tool(run_command_json, repo_root: Path, name: str, arguments: dict[str, Any]) -> str:
    if name == "worktree_guard":
        return await worktree_guard(
            run_command_json,
            repo_root,
            module_key=arguments.get("module_key", ""),
            allowed_prefixes=arguments.get("allowed_prefixes", ""),
            forbidden_prefixes=arguments.get("forbidden_prefixes", ""),
            include_untracked=bool(arguments.get("include_untracked", True)),
        )
    raise ValueError(f"未知工作区工具: {name}")
