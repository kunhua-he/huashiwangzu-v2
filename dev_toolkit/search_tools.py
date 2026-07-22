"""Fast content search tools for the project toolkit MCP."""

from __future__ import annotations

import asyncio
import json
import re
import shutil
from pathlib import Path
from typing import Any

try:
    from dev_toolkit.code_tools import resolve_repo_path
except ModuleNotFoundError:
    from code_tools import resolve_repo_path

TOOL_NAMES = {"rg_search"}

_DEFAULT_EXCLUDES = (
    ".git",
    "node_modules",
    ".venv",
    "backend/.venv",
    "dist",
    "build",
    ".codegraph",
    "__pycache__",
    ".pytest_cache",
    "memory_embeddings.json",
    "backend/logs",
    "backend/data/uploads",
)


def tool_definitions() -> list[Any]:
    from mcp.types import Tool

    return [
        Tool(
            name="rg_search",
            description=(
                "仓库内结构化内容搜索（优先 ripgrep）。支持 path/glob 限定与固定排除大目录，"
                "用于快速定位字符串/错误信息，避免反复 shell 试探。"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "搜索正则/字符串"},
                    "path": {
                        "type": "string",
                        "description": "搜索根路径（相对仓库根），默认仓库根",
                        "default": "",
                    },
                    "glob": {
                        "type": "string",
                        "description": "文件 glob，如 *.py 或 modules/knowledge/**",
                        "default": "",
                    },
                    "max_matches": {
                        "type": "number",
                        "description": "最多返回命中行数",
                        "default": 30,
                    },
                    "context": {
                        "type": "number",
                        "description": "命中行前后上下文行数 0-3",
                        "default": 0,
                    },
                    "case_insensitive": {
                        "type": "boolean",
                        "description": "忽略大小写",
                        "default": False,
                    },
                },
                "required": ["pattern"],
            },
        ),
    ]


def handles_tool(name: str) -> bool:
    return name in TOOL_NAMES


async def handle_tool(repo_root: Path, name: str, arguments: dict[str, Any]) -> str:
    if name == "rg_search":
        return await rg_search(
            repo_root,
            pattern=str(arguments["pattern"]),
            path=str(arguments.get("path") or ""),
            glob=str(arguments.get("glob") or ""),
            max_matches=int(arguments.get("max_matches") or 30),
            context=int(arguments.get("context") or 0),
            case_insensitive=bool(arguments.get("case_insensitive", False)),
        )
    raise ValueError(f"未知搜索工具: {name}")


async def rg_search(
    repo_root: Path,
    pattern: str,
    path: str = "",
    glob: str = "",
    max_matches: int = 30,
    context: int = 0,
    case_insensitive: bool = False,
) -> str:
    if not pattern:
        return json.dumps({"success": False, "error": "pattern is required"}, ensure_ascii=False)

    root = repo_root.resolve()
    search_root = root
    if path.strip():
        try:
            search_root = resolve_repo_path(repo_root, path.strip())
        except ValueError as exc:
            return json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False)
        if not search_root.exists():
            return json.dumps(
                {"success": False, "error": f"path does not exist: {path}"},
                ensure_ascii=False,
            )

    limit = max(1, min(int(max_matches or 30), 200))
    ctx = max(0, min(int(context or 0), 3))
    rg_bin = shutil.which("rg")
    if rg_bin:
        matches, command, engine = await _search_with_rg(
            rg_bin,
            root,
            search_root,
            pattern,
            glob=glob,
            limit=limit,
            context=ctx,
            case_insensitive=case_insensitive,
        )
    else:
        matches, command, engine = await _search_with_grep(
            root,
            search_root,
            pattern,
            glob=glob,
            limit=limit,
            case_insensitive=case_insensitive,
        )

    return json.dumps(
        {
            "success": True,
            "engine": engine,
            "pattern": pattern,
            "path": str(search_root.relative_to(root)) if search_root != root else ".",
            "glob": glob or None,
            "match_count": len(matches),
            "truncated": len(matches) >= limit,
            "max_matches": limit,
            "command": command,
            "matches": matches,
            "hint": "定位到文件后用 code_node/quick_fix_*; 改完用 select_verify → run_tests_parallel。",
        },
        ensure_ascii=False,
        indent=2,
    )


async def _search_with_rg(
    rg_bin: str,
    repo_root: Path,
    search_root: Path,
    pattern: str,
    *,
    glob: str,
    limit: int,
    context: int,
    case_insensitive: bool,
) -> tuple[list[dict[str, Any]], list[str], str]:
    cmd = [
        rg_bin,
        "--line-number",
        "--no-heading",
        "--color",
        "never",
        "--max-count",
        str(limit),
    ]
    if case_insensitive:
        cmd.append("-i")
    if context:
        cmd.extend(["-C", str(context)])
    for exclude in _DEFAULT_EXCLUDES:
        cmd.extend(["--glob", f"!{exclude}"])
        cmd.extend(["--glob", f"!**/{exclude}/**"])
    if glob:
        cmd.extend(["--glob", glob])
    cmd.extend(["--", pattern, str(search_root)])

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(repo_root),
    )
    stdout, stderr = await proc.communicate()
    text = (stdout or b"").decode("utf-8", errors="replace")
    # rg returns 1 when no matches — still success for our tool
    if proc.returncode not in (0, 1):
        err = (stderr or b"").decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"rg failed ({proc.returncode}): {err}")

    matches = _parse_rg_lines(text, repo_root, limit)
    return matches, cmd, "rg"


async def _search_with_grep(
    repo_root: Path,
    search_root: Path,
    pattern: str,
    *,
    glob: str,
    limit: int,
    case_insensitive: bool,
) -> tuple[list[dict[str, Any]], list[str], str]:
    """Fallback when ripgrep is unavailable."""
    cmd = ["grep", "-R", "-n", "-I"]
    if case_insensitive:
        cmd.append("-i")
    for exclude in _DEFAULT_EXCLUDES:
        cmd.append(f"--exclude-dir={Path(exclude).name}")
        cmd.append(f"--exclude={Path(exclude).name}")
    if glob:
        cmd.append(f"--include={glob}")
    cmd.extend(["--", pattern, str(search_root)])

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(repo_root),
    )
    stdout, _stderr = await proc.communicate()
    text = (stdout or b"").decode("utf-8", errors="replace")
    matches = _parse_rg_lines(text, repo_root, limit)
    return matches, cmd, "grep"


_RG_LINE = re.compile(r"^(.*?):(\d+)[:-](.*)$")


def _parse_rg_lines(text: str, repo_root: Path, limit: int) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    root = repo_root.resolve()
    for raw in text.splitlines():
        if not raw.strip() or raw.startswith("--"):
            continue
        m = _RG_LINE.match(raw)
        if not m:
            continue
        file_part, line_s, content = m.group(1), m.group(2), m.group(3)
        path = Path(file_part)
        try:
            if path.is_absolute():
                rel = str(path.resolve().relative_to(root))
            else:
                rel = str((root / path).resolve().relative_to(root)) if path.parts else file_part
        except ValueError:
            rel = file_part
        matches.append(
            {
                "file": rel,
                "line": int(line_s),
                "text": content,
            }
        )
        if len(matches) >= limit:
            break
    return matches
