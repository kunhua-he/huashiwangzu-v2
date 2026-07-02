"""Code exploration, patching, linting, and test tools for the project toolkit."""

import asyncio
import json
import shlex
from pathlib import Path
from typing import Any

try:
    from dev_toolkit.quick_fix import quick_fix_patch, quick_fix_preview
except ModuleNotFoundError:
    from quick_fix import quick_fix_patch, quick_fix_preview


TOOL_NAMES = {
    "code_explore",
    "code_node",
    "code_impact",
    "quick_fix_preview",
    "apply_patch",
    "quick_fix_patch",
    "lint",
    "run_test",
}


def tail_text(text: str, limit: int = 8000) -> str:
    if len(text) <= limit:
        return text
    return text[-limit:]


def repo_relative(repo_root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo_root))
    except ValueError:
        return str(path)


def resolve_repo_path(repo_root: Path, path: str, *, base_dir: Path | None = None) -> Path:
    raw = Path(path).expanduser()
    if raw.is_absolute():
        resolved = raw.resolve()
    else:
        base = base_dir or repo_root
        resolved = (base / raw).resolve()
    if repo_root.resolve() not in resolved.parents and resolved != repo_root.resolve():
        raise ValueError(f"路径必须在仓库内: {path}")
    return resolved


def normalize_pytest_targets(repo_root: Path, target: str) -> list[str]:
    backend_dir = repo_root / "backend"
    normalized: list[str] = []
    for raw_part in shlex.split(target):
        path_part, sep, suffix = raw_part.partition("::")
        if not path_part:
            continue
        try:
            resolved = resolve_repo_path(repo_root, path_part, base_dir=backend_dir)
        except ValueError:
            normalized.append(raw_part)
            continue
        if resolved.exists():
            try:
                rel = resolved.relative_to(backend_dir)
                normalized.append(str(rel) + (sep + suffix if sep else ""))
                continue
            except ValueError:
                normalized.append(str(resolved) + (sep + suffix if sep else ""))
                continue
        if path_part.startswith("backend/"):
            normalized.append(path_part.removeprefix("backend/") + (sep + suffix if sep else ""))
        else:
            normalized.append(raw_part)
    return normalized


async def code_explore(codegraph_cli: str, query: str) -> str:
    cmd = [codegraph_cli, "explore", query]
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        return json.dumps({"error": f"codegraph explore 失败: {stderr.decode()[:500]}"}, ensure_ascii=False)
    return stdout.decode() or "(空结果)"


async def code_node(codegraph_cli: str, symbol: str) -> str:
    cmd = [codegraph_cli, "node", symbol]
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        return json.dumps({"error": f"codegraph node 失败: {stderr.decode()[:500]}"}, ensure_ascii=False)
    return stdout.decode() or "(空结果)"


async def code_impact(codegraph_cli: str, path: str) -> str:
    cmd = [codegraph_cli, "impact", path]
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        fallback = [codegraph_cli, "node", path]
        proc2 = await asyncio.create_subprocess_exec(
            *fallback, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout2, stderr2 = await proc2.communicate()
        if proc2.returncode != 0:
            return json.dumps({"error": f"codegraph impact 失败(无fallback): {stderr.decode()[:500]}; {stderr2.decode()[:500]}"}, ensure_ascii=False)
        return stdout2.decode() or "(空结果)"
    return stdout.decode() or "(空结果)"


async def lint(run_command_json, repo_root: Path, ruff_cli: str, path: str, diff: bool = False) -> str:
    try:
        abs_path = resolve_repo_path(repo_root, path)
    except ValueError as exc:
        return json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False)
    if not abs_path.is_file():
        return json.dumps({"success": False, "error": f"文件不存在: {abs_path}"}, ensure_ascii=False)
    cmd = [ruff_cli, "check"]
    if diff:
        cmd.extend(["--diff"])
    cmd.append(str(abs_path))
    result = await run_command_json(cmd, cwd=repo_root, timeout=60)
    output = (result.get("stdout") or "") + (result.get("stderr") or "")
    payload = {
        "success": result.get("success", False),
        "path": repo_relative(repo_root, abs_path),
        "diff": diff,
        "command": result.get("command"),
        "cwd": result.get("cwd"),
        "duration_seconds": result.get("duration_seconds"),
        "output": output or "All checks passed!",
        "output_tail": tail_text(output) if output else "All checks passed!",
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


async def run_test(run_command_json, repo_root: Path, target: str, timeout: int = 120) -> str:
    normalized_targets = normalize_pytest_targets(repo_root, target)
    backend_dir = repo_root / "backend"
    cmd = [str(backend_dir / ".venv" / "bin" / "pytest"), *normalized_targets]
    result = await run_command_json(cmd, cwd=backend_dir, timeout=timeout)
    return json.dumps({
        "success": result.get("success", False),
        "target": target,
        "normalized_targets": normalized_targets,
        "command": cmd,
        "cwd": result.get("cwd"),
        "duration_seconds": result.get("duration_seconds"),
        "returncode": result.get("returncode"),
        "stdout": result.get("stdout", ""),
        "stderr": result.get("stderr", ""),
        "stdout_tail": result.get("stdout_tail", ""),
        "stderr_tail": result.get("stderr_tail", ""),
        "timeout": result.get("timeout", False),
        "timeout_seconds": result.get("timeout_seconds"),
    }, ensure_ascii=False, indent=2)


def tool_definitions() -> list[Any]:
    from mcp.types import Tool

    quick_fix_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "仓库内文件路径(绝对或相对仓库根)"},
            "old_text": {"type": "string", "description": "必须唯一命中的原文块"},
            "new_text": {"type": "string", "description": "替换后的文本块"},
            "start_line": {"type": "number", "description": "可选: CodeGraph 定位起始行"},
            "end_line": {"type": "number", "description": "可选: CodeGraph 定位结束行"},
            "expected_old_text_sha256": {
                "type": "string",
                "description": "可选: old_text 的 sha256, 防止调用方传错块",
                "default": "",
            },
        },
        "required": ["path", "old_text", "new_text"],
    }
    return [
        Tool(
            name="code_explore",
            description="通过 codegraph 探索代码: 查符号/调用链/影响面. shell: codegraph explore <query>",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "符号名/文件名/自然语言问题"},
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="code_node",
            description="通过 codegraph 查符号或文件的定义. shell: codegraph node <symbol>",
            inputSchema={
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "符号名或文件路径"},
                },
                "required": ["symbol"],
            },
        ),
        Tool(
            name="code_impact",
            description="通过 codegraph 查文件改动的影响面. shell: codegraph impact <path>",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "文件路径"},
                },
                "required": ["path"],
            },
        ),
        Tool(
            name="quick_fix_preview",
            description="预览精准补丁: path + old_text + new_text 精确替换，可带 start_line/end_line 和 old_text sha256 防漂移; 不写盘.",
            inputSchema=quick_fix_schema,
        ),
        Tool(
            name="apply_patch",
            description="应用精准补丁(同 quick_fix_patch): path + old_text + new_text 精确替换，仅 old_text 唯一命中时原子写盘.",
            inputSchema=quick_fix_schema,
        ),
        Tool(
            name="quick_fix_patch",
            description="应用精准补丁: 与 quick_fix_preview 同校验，仅 old_text 唯一命中时原子写盘.",
            inputSchema=quick_fix_schema,
        ),
        Tool(
            name="lint",
            description="用 ruff 静态检查 Python 文件。支持 diff=true 只预览可修复 diff，不写盘。",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Python 文件路径(绝对或相对仓库根)"},
                    "diff": {"type": "boolean", "description": "只返回 ruff --diff 预览", "default": False},
                },
                "required": ["path"],
            },
        ),
        Tool(
            name="run_test",
            description="跑单个测试目标，自动兼容 backend/tests、tests、绝对路径，返回结构化结果。",
            inputSchema={
                "type": "object",
                "properties": {
                    "target": {"type": "string", "description": "测试目标, 如 backend/tests/test_auth.py、tests/test_auth.py 或 tests/test_auth.py::test_login"},
                    "timeout": {"type": "number", "description": "超时秒数", "default": 120},
                },
                "required": ["target"],
            },
        ),
    ]


def handles_tool(name: str) -> bool:
    return name in TOOL_NAMES


async def handle_tool(
    run_command_json,
    repo_root: Path,
    codegraph_cli: str,
    ruff_cli: str,
    name: str,
    arguments: dict[str, Any],
) -> str:
    if name == "code_explore":
        return await code_explore(codegraph_cli, query=arguments["query"])
    if name == "code_node":
        return await code_node(codegraph_cli, symbol=arguments["symbol"])
    if name == "code_impact":
        return await code_impact(codegraph_cli, path=arguments["path"])
    if name == "quick_fix_preview":
        return json.dumps(
            quick_fix_preview(
                repo_root=repo_root,
                path=arguments["path"],
                old_text=arguments["old_text"],
                new_text=arguments["new_text"],
                start_line=arguments.get("start_line"),
                end_line=arguments.get("end_line"),
                expected_old_text_sha256=arguments.get("expected_old_text_sha256", ""),
            ),
            ensure_ascii=False,
            indent=2,
        )
    if name in {"apply_patch", "quick_fix_patch"}:
        return json.dumps(
            quick_fix_patch(
                repo_root=repo_root,
                path=arguments["path"],
                old_text=arguments["old_text"],
                new_text=arguments["new_text"],
                start_line=arguments.get("start_line"),
                end_line=arguments.get("end_line"),
                expected_old_text_sha256=arguments.get("expected_old_text_sha256", ""),
            ),
            ensure_ascii=False,
            indent=2,
        )
    if name == "lint":
        return await lint(run_command_json, repo_root, ruff_cli, path=arguments["path"], diff=bool(arguments.get("diff", False)))
    if name == "run_test":
        return await run_test(run_command_json, repo_root, target=arguments["target"], timeout=int(arguments.get("timeout", 120)))
    raise ValueError(f"未知代码工具: {name}")
