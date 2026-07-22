"""Code exploration, patching, linting, and test tools for the project toolkit."""

import asyncio
import json
import os
import re
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
    "run_tests_parallel",
}

# Heuristic: these tend to share live backend / DB and should not fan out hard.
_SERIAL_TEST_MARKERS = (
    "e2e",
    "live",
    "release_gate",
    "serial_db",
    "smoke",
    "integration",
)

_MAX_PARALLEL_WORKERS = 8
_DEFAULT_PARALLEL_WORKERS = 4


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


def split_path_list(raw: str | list[str] | tuple[str, ...] | None) -> list[str]:
    """Split path input from MCP (string / JSON list / native list)."""
    if raw is None:
        return []
    if isinstance(raw, (list, tuple)):
        items: list[str] = []
        for item in raw:
            items.extend(split_path_list(str(item)))
        return items
    text = str(raw).strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, list):
        return [str(item).strip() for item in parsed if str(item).strip()]

    # MCP / Python repr sometimes arrives as "['a.py', 'b.py']" (invalid JSON).
    if text.startswith("[") and text.endswith("]") and ("'" in text or '"' in text):
        inner = text[1:-1].strip()
        if inner:
            recovered = [part.strip().strip("'\"") for part in re.split(r"\s*,\s*", inner)]
            recovered = [part for part in recovered if part]
            if recovered:
                return recovered

    items = []
    for chunk in re.split(r"[,\n]", text):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            parts = shlex.split(chunk)
        except ValueError:
            parts = [chunk]
        items.extend(part.strip() for part in parts if part.strip())
    return items


def normalize_pytest_targets(repo_root: Path, target: str) -> list[str]:
    backend_dir = repo_root / "backend"
    normalized: list[str] = []
    for raw_part in shlex.split(target):
        path_part, sep, suffix = raw_part.partition("::")
        if not path_part:
            continue
        suffix_text = sep + suffix if sep else ""
        if path_part.startswith("backend/"):
            backend_relative = path_part.removeprefix("backend/")
            if (backend_dir / backend_relative).exists():
                normalized.append(backend_relative + suffix_text)
                continue
            repo_relative = repo_root / backend_relative
            if repo_relative.exists():
                normalized.append(str(repo_relative) + suffix_text)
                continue
            normalized.append(backend_relative + suffix_text)
            continue
        try:
            repo_resolved = resolve_repo_path(repo_root, path_part)
            if repo_resolved.exists():
                try:
                    rel = repo_resolved.relative_to(backend_dir)
                    normalized.append(str(rel) + suffix_text)
                except ValueError:
                    normalized.append(str(repo_resolved) + suffix_text)
                continue
        except ValueError:
            normalized.append(raw_part)
            continue
        try:
            resolved = resolve_repo_path(repo_root, path_part, base_dir=backend_dir)
        except ValueError:
            normalized.append(raw_part)
            continue
        if resolved.exists():
            try:
                rel = resolved.relative_to(backend_dir)
                normalized.append(str(rel) + suffix_text)
                continue
            except ValueError:
                normalized.append(str(resolved) + suffix_text)
                continue
        normalized.append(raw_part)
    return normalized


def pytest_targets_for_command(backend_dir: Path, normalized_targets: list[str]) -> list[str]:
    if not any(Path(item.partition("::")[0]).is_absolute() for item in normalized_targets):
        return normalized_targets
    command_targets: list[str] = []
    for item in normalized_targets:
        path_part, sep, suffix = item.partition("::")
        suffix_text = sep + suffix if sep else ""
        if Path(path_part).is_absolute():
            command_targets.append(item)
        else:
            command_targets.append(str(backend_dir / path_part) + suffix_text)
    return command_targets


async def code_explore(
    codegraph_cli: str,
    query: str,
    path: str = "",
    max_files: int | None = None,
) -> str:
    cmd = [codegraph_cli, "explore", query]
    if path:
        cmd.extend(["--path", path])
    if max_files is not None:
        cmd.extend(["--max-files", str(int(max_files))])
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        return json.dumps(
            {
                "error": f"codegraph explore 失败: {stderr.decode()[:500]}",
                "command": cmd,
            },
            ensure_ascii=False,
        )
    return stdout.decode() or "(空结果)"


async def code_node(codegraph_cli: str, symbol: str, file: str = "") -> str:
    cmd = [codegraph_cli, "node", symbol]
    if file:
        cmd.extend(["--file", file])
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        return json.dumps(
            {
                "error": f"codegraph node 失败: {stderr.decode()[:500]}",
                "command": cmd,
            },
            ensure_ascii=False,
        )
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


async def lint_one(run_command_json, repo_root: Path, ruff_cli: str, path: str, diff: bool = False) -> dict[str, Any]:
    try:
        abs_path = resolve_repo_path(repo_root, path)
    except ValueError as exc:
        return {"success": False, "path": path, "error": str(exc)}
    if not abs_path.exists():
        return {"success": False, "path": path, "error": f"路径不存在: {abs_path}"}
    if not abs_path.is_file() and not abs_path.is_dir():
        return {"success": False, "path": path, "error": f"不是文件或目录: {abs_path}"}
    cmd = [ruff_cli, "check"]
    if diff:
        cmd.extend(["--diff"])
    cmd.append(str(abs_path))
    result = await run_command_json(cmd, cwd=repo_root, timeout=60)
    output = (result.get("stdout") or "") + (result.get("stderr") or "")
    return {
        "success": result.get("success", False),
        "path": repo_relative(repo_root, abs_path),
        "is_dir": abs_path.is_dir(),
        "diff": diff,
        "command": result.get("command"),
        "cwd": result.get("cwd"),
        "duration_seconds": result.get("duration_seconds"),
        "output": output or "All checks passed!",
        "output_tail": tail_text(output) if output else "All checks passed!",
    }


async def lint(
    run_command_json,
    repo_root: Path,
    ruff_cli: str,
    path: str | list[str],
    diff: bool = False,
    max_workers: int = _DEFAULT_PARALLEL_WORKERS,
) -> str:
    paths = split_path_list(path)
    if not paths:
        return json.dumps({"success": False, "error": "path is required"}, ensure_ascii=False)
    workers = max(1, min(int(max_workers or _DEFAULT_PARALLEL_WORKERS), _MAX_PARALLEL_WORKERS))
    if len(paths) == 1:
        return json.dumps(
            await lint_one(run_command_json, repo_root, ruff_cli, paths[0], diff),
            ensure_ascii=False,
            indent=2,
        )
    sem = asyncio.Semaphore(workers)

    async def _one(item: str) -> dict[str, Any]:
        async with sem:
            return await lint_one(run_command_json, repo_root, ruff_cli, item, diff)

    results = await asyncio.gather(*[_one(item) for item in paths])
    payload = {
        "success": all(item.get("success") for item in results),
        "paths": [item.get("path", "") for item in results],
        "diff": diff,
        "max_workers": workers,
        "results": results,
        "failed_count": sum(1 for item in results if not item.get("success")),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def split_test_targets(raw: str | list[str] | None) -> list[str]:
    """Split multi-target input into discrete pytest target tokens."""
    if raw is None:
        return []
    if isinstance(raw, list):
        items: list[str] = []
        for item in raw:
            items.extend(split_test_targets(str(item)))
        return items
    text = str(raw).strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, list):
        return [str(item).strip() for item in parsed if str(item).strip()]
    # Prefer split_path_list for comma/newline/json; also keep shlex multi-path string.
    from_list = split_path_list(text)
    if len(from_list) > 1:
        return from_list
    try:
        parts = shlex.split(text)
    except ValueError:
        parts = [text]
    return [part.strip() for part in parts if part.strip()]


def is_serial_preferred_target(target: str) -> bool:
    lowered = target.lower().replace("\\", "/")
    return any(marker in lowered for marker in _SERIAL_TEST_MARKERS)


def _build_pytest_command(
    repo_root: Path,
    target: str,
) -> tuple[list[str], Path, list[str]]:
    """Return (cmd, cwd, normalized_targets) for one discrete target string."""
    normalized_targets = normalize_pytest_targets(repo_root, target)
    if not normalized_targets:
        raise ValueError(f"empty pytest target: {target!r}")
    backend_dir = repo_root / "backend"
    command_targets = pytest_targets_for_command(backend_dir, normalized_targets)
    cmd = [str(backend_dir / ".venv" / "bin" / "pytest"), *command_targets]
    cwd = backend_dir
    if any(Path(item.partition("::")[0]).is_absolute() for item in command_targets):
        cwd = repo_root
        pythonpath = str(repo_root)
        if os.environ.get("PYTHONPATH"):
            pythonpath = f"{pythonpath}:{os.environ['PYTHONPATH']}"
        cmd = ["env", f"PYTHONPATH={pythonpath}", *cmd]
    return cmd, cwd, normalized_targets


async def _run_one_pytest(
    run_command_json,
    repo_root: Path,
    target: str,
    timeout: int = 120,
    env: dict[str, str] | None = None,
    *,
    include_full_output: bool = False,
) -> dict[str, Any]:
    try:
        cmd, cwd, normalized_targets = _build_pytest_command(repo_root, target)
    except ValueError as exc:
        return {
            "success": False,
            "target": target,
            "error": str(exc),
            "duration_seconds": 0.0,
            "serial_preferred": is_serial_preferred_target(target),
        }
    if env:
        result = await run_command_json(cmd, cwd=cwd, timeout=timeout, env={**os.environ, **env})
    else:
        result = await run_command_json(cmd, cwd=cwd, timeout=timeout)
    stdout = result.get("stdout", "") or ""
    stderr = result.get("stderr", "") or ""
    payload: dict[str, Any] = {
        "success": bool(result.get("success", False)),
        "target": target,
        "normalized_targets": normalized_targets,
        "command": cmd,
        "cwd": result.get("cwd") or str(cwd),
        "duration_seconds": result.get("duration_seconds"),
        "returncode": result.get("returncode"),
        "stdout_tail": result.get("stdout_tail") or tail_text(stdout, 4000),
        "stderr_tail": result.get("stderr_tail") or tail_text(stderr, 2000),
        "timeout": result.get("timeout", False),
        "timeout_seconds": result.get("timeout_seconds"),
        "serial_preferred": is_serial_preferred_target(target),
    }
    if include_full_output:
        payload["stdout"] = stdout
        payload["stderr"] = stderr
    return payload


async def run_test(
    run_command_json,
    repo_root: Path,
    target: str,
    timeout: int = 120,
    env: dict[str, str] | None = None,
) -> str:
    """Run one pytest process (multi-path targets stay in a single process)."""
    one = await _run_one_pytest(
        run_command_json,
        repo_root,
        target,
        timeout=timeout,
        env=env,
        include_full_output=True,
    )
    payload = {
        "success": one.get("success", False),
        "target": target,
        "normalized_targets": one.get("normalized_targets") or [],
        "command": one.get("command") or [],
        "env_keys": sorted(env.keys()) if env else [],
        "cwd": one.get("cwd"),
        "duration_seconds": one.get("duration_seconds"),
        "returncode": one.get("returncode"),
        "stdout": one.get("stdout", ""),
        "stderr": one.get("stderr", ""),
        "stdout_tail": one.get("stdout_tail", ""),
        "stderr_tail": one.get("stderr_tail", ""),
        "timeout": one.get("timeout", False),
        "timeout_seconds": one.get("timeout_seconds"),
    }
    if one.get("error"):
        payload["error"] = one["error"]
    return json.dumps(payload, ensure_ascii=False, indent=2)


async def run_tests_parallel(
    run_command_json,
    repo_root: Path,
    targets: str | list[str],
    max_workers: int = _DEFAULT_PARALLEL_WORKERS,
    timeout_per_target: int = 120,
    mode: str = "auto",
    env: dict[str, str] | None = None,
) -> str:
    """Fan-out discrete pytest targets with process isolation and optional serial bucket."""
    import time

    started = time.monotonic()
    items = split_test_targets(targets)
    if not items:
        return json.dumps(
            {"success": False, "error": "targets is required", "results": []},
            ensure_ascii=False,
            indent=2,
        )
    workers = max(1, min(int(max_workers or _DEFAULT_PARALLEL_WORKERS), _MAX_PARALLEL_WORKERS))
    mode_norm = (mode or "auto").strip().lower()
    if mode_norm not in {"auto", "force_parallel", "serial"}:
        mode_norm = "auto"

    if mode_norm == "serial":
        parallel_items: list[str] = []
        serial_items = items
    elif mode_norm == "force_parallel":
        parallel_items = items
        serial_items = []
    else:
        parallel_items = [t for t in items if not is_serial_preferred_target(t)]
        serial_items = [t for t in items if is_serial_preferred_target(t)]

    results: list[dict[str, Any]] = []
    sem = asyncio.Semaphore(workers)

    async def _parallel_one(target: str) -> dict[str, Any]:
        async with sem:
            return await _run_one_pytest(
                run_command_json,
                repo_root,
                target,
                timeout=timeout_per_target,
                env=env,
            )

    if parallel_items:
        results.extend(await asyncio.gather(*[_parallel_one(t) for t in parallel_items]))

    for target in serial_items:
        results.append(
            await _run_one_pytest(
                run_command_json,
                repo_root,
                target,
                timeout=timeout_per_target,
                env=env,
            )
        )

    # Preserve input order in results
    by_target = {str(item.get("target")): item for item in results}
    ordered = [by_target[t] for t in items if t in by_target]
    # Append any unexpected extras
    for item in results:
        if item not in ordered:
            ordered.append(item)

    passed = sum(1 for item in ordered if item.get("success"))
    failed = len(ordered) - passed
    wall = round(time.monotonic() - started, 3)
    payload = {
        "success": failed == 0 and len(ordered) > 0,
        "passed": passed,
        "failed": failed,
        "total": len(ordered),
        "duration_seconds": wall,
        "max_workers": workers,
        "mode": mode_norm,
        "parallel_count": len(parallel_items),
        "serial_count": len(serial_items),
        "targets": items,
        "failed_targets": [item.get("target") for item in ordered if not item.get("success")],
        "results": ordered,
        "env_keys": sorted(env.keys()) if env else [],
        "hint": "优先 select_verify → run_tests_parallel；e2e/live 默认进串行桶。",
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


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
            description="通过 codegraph 探索代码: 查符号/调用链/影响面. shell: codegraph explore <query> [--path] [--max-files]",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "符号名/文件名/自然语言问题"},
                    "path": {"type": "string", "description": "可选: 限定目录/文件前缀", "default": ""},
                    "max_files": {"type": "number", "description": "可选: 最多返回相关文件数"},
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="code_node",
            description="通过 codegraph 查符号或文件的定义. shell: codegraph node <symbol> [--file]",
            inputSchema={
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "符号名或文件路径"},
                    "file": {"type": "string", "description": "可选: 限定到某个文件", "default": ""},
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
            description="用 ruff 静态检查 Python 文件或目录。path 支持单路径/目录/逗号换行/JSON list；多路径有限并行；diff=true 只预览。",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "description": "Python 文件或目录(绝对或相对仓库根)；字符串(逗号/换行/JSON list)或 string 数组",
                        "anyOf": [
                            {"type": "string"},
                            {"type": "array", "items": {"type": "string"}},
                        ],
                    },
                    "diff": {"type": "boolean", "description": "只返回 ruff --diff 预览", "default": False},
                    "max_workers": {"type": "number", "description": "多路径并行上限", "default": 4},
                },
                "required": ["path"],
            },
        ),
        Tool(
            name="run_test",
            description=(
                "跑一个 pytest 进程。target 可含多个路径(空格分隔，仍同进程串行执行)。"
                "多个独立目标要并行请用 run_tests_parallel。"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "target": {"type": "string", "description": "测试目标, 如 backend/tests/test_auth.py 或 tests/test_auth.py::test_login"},
                    "timeout": {"type": "number", "description": "超时秒数", "default": 120},
                },
                "required": ["target"],
            },
        ),
        Tool(
            name="run_tests_parallel",
            description=(
                "并行跑多组 pytest 目标（每目标独立进程）。mode=auto 时 e2e/live/smoke 等进串行桶；"
                "返回墙钟耗时与每目标 tail。优先配合 select_verify 使用。"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "targets": {
                        "description": "多个目标：字符串(空格/逗号/换行/JSON list)或 string 数组",
                        "anyOf": [
                            {"type": "string"},
                            {"type": "array", "items": {"type": "string"}},
                        ],
                    },
                    "max_workers": {"type": "number", "description": "并行进程上限(1-8)", "default": 4},
                    "timeout_per_target": {"type": "number", "description": "每个目标超时秒数", "default": 120},
                    "mode": {
                        "type": "string",
                        "description": "auto|force_parallel|serial",
                        "default": "auto",
                    },
                },
                "required": ["targets"],
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
        max_files = arguments.get("max_files")
        return await code_explore(
            codegraph_cli,
            query=arguments["query"],
            path=str(arguments.get("path") or ""),
            max_files=int(max_files) if max_files is not None and max_files != "" else None,
        )
    if name == "code_node":
        return await code_node(
            codegraph_cli,
            symbol=arguments["symbol"],
            file=str(arguments.get("file") or ""),
        )
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
        return await lint(
            run_command_json,
            repo_root,
            ruff_cli,
            path=arguments["path"],
            diff=bool(arguments.get("diff", False)),
            max_workers=int(arguments.get("max_workers", _DEFAULT_PARALLEL_WORKERS)),
        )
    if name == "run_test":
        return await run_test(
            run_command_json,
            repo_root,
            target=arguments["target"],
            timeout=int(arguments.get("timeout", 120)),
        )
    if name == "run_tests_parallel":
        return await run_tests_parallel(
            run_command_json,
            repo_root,
            targets=arguments["targets"],  # split_test_targets accepts list|str
            max_workers=int(arguments.get("max_workers", _DEFAULT_PARALLEL_WORKERS)),
            timeout_per_target=int(arguments.get("timeout_per_target", 120)),
            mode=str(arguments.get("mode") or "auto"),
        )
    raise ValueError(f"未知代码工具: {name}")
