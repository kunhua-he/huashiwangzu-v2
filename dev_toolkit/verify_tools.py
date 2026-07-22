"""Change-aware verify target selection for the project toolkit MCP."""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import Any

try:
    from dev_toolkit.code_tools import (
        is_serial_preferred_target,
        split_path_list,
        split_test_targets,
    )
    from dev_toolkit.worktree_tools import git_changed_entries
except ModuleNotFoundError:
    from code_tools import (
        is_serial_preferred_target,
        split_path_list,
        split_test_targets,
    )
    from worktree_tools import git_changed_entries

TOOL_NAMES = {"select_verify"}

_MAX_TEST_TARGETS = 40
_MAX_MODULE_TESTS = 12


def tool_definitions() -> list[Any]:
    from mcp.types import Tool

    return [
        Tool(
            name="select_verify",
            description=(
                "根据改动路径（或当前 git dirty）推断 lint_paths 与 pytest targets，"
                "并分 parallel_safe / serial_preferred。输出可直接喂给 lint 与 run_tests_parallel。"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "paths": {
                        "description": "改动文件列表：字符串(空格/逗号/换行/JSON list)或 string 数组。可与 from_git 并用。",
                        "anyOf": [
                            {"type": "string"},
                            {"type": "array", "items": {"type": "string"}},
                        ],
                        "default": "",
                    },
                    "from_git": {
                        "type": "boolean",
                        "description": "从 git status 收集 dirty 路径",
                        "default": False,
                    },
                    "extra_targets": {
                        "description": "额外 pytest 目标，合并进结果（字符串或数组）",
                        "anyOf": [
                            {"type": "string"},
                            {"type": "array", "items": {"type": "string"}},
                        ],
                        "default": "",
                    },
                    "include_codegraph_affected": {
                        "type": "boolean",
                        "description": "若本机有 codegraph affected 则尝试补充测试路径",
                        "default": True,
                    },
                },
            },
        ),
    ]


def handles_tool(name: str) -> bool:
    return name in TOOL_NAMES


async def handle_tool(
    run_command_json,
    repo_root: Path,
    codegraph_cli: str,
    name: str,
    arguments: dict[str, Any],
) -> str:
    if name == "select_verify":
        raw_paths = arguments.get("paths")
        if raw_paths is None:
            paths_arg: str | list[str] = ""
        elif isinstance(raw_paths, (list, tuple)):
            paths_arg = [str(item) for item in raw_paths]
        else:
            paths_arg = raw_paths
        raw_extra = arguments.get("extra_targets")
        if raw_extra is None:
            extra_arg: str | list[str] = ""
        elif isinstance(raw_extra, (list, tuple)):
            extra_arg = [str(item) for item in raw_extra]
        else:
            extra_arg = raw_extra
        return await select_verify(
            run_command_json,
            repo_root,
            codegraph_cli=codegraph_cli,
            paths=paths_arg,
            from_git=bool(arguments.get("from_git", False)),
            extra_targets=extra_arg,
            include_codegraph_affected=bool(arguments.get("include_codegraph_affected", True)),
        )
    raise ValueError(f"未知 verify 工具: {name}")


async def select_verify(
    run_command_json,
    repo_root: Path,
    *,
    codegraph_cli: str = "codegraph",
    paths: str | list[str] = "",
    from_git: bool = False,
    extra_targets: str | list[str] = "",
    include_codegraph_affected: bool = True,
) -> str:
    notes: list[str] = []
    changed: list[str] = []

    for item in split_path_list(paths):
        normalized = item.strip().lstrip("./")
        if normalized and normalized not in changed:
            changed.append(normalized)

    if from_git:
        try:
            entries = await git_changed_entries(run_command_json, repo_root, include_untracked=True)
            for entry in entries:
                p = str(entry.get("path") or "").strip().lstrip("./")
                if p and p not in changed:
                    changed.append(p)
            notes.append(f"git_dirty={len(entries)}")
        except Exception as exc:  # noqa: BLE001 — surface soft failure
            notes.append(f"git_status_failed:{exc}")

    has_extra = bool(split_test_targets(extra_targets))
    if not changed and not has_extra:
        return json.dumps(
            {
                "success": False,
                "error": "需要 paths 或 from_git=true 或 extra_targets",
                "lint_paths": [],
                "test_targets": [],
                "parallel_safe": [],
                "serial_preferred": [],
                "notes": notes,
            },
            ensure_ascii=False,
            indent=2,
        )

    lint_paths: list[str] = []
    test_targets: list[str] = []

    for path in changed:
        for lint_path in _lint_candidates(repo_root, path):
            if lint_path not in lint_paths:
                lint_paths.append(lint_path)
        for test_path in _heuristic_tests_for_path(repo_root, path):
            if test_path not in test_targets:
                test_targets.append(test_path)

    if include_codegraph_affected and changed:
        affected, affected_note = await _codegraph_affected(repo_root, codegraph_cli, changed)
        if affected_note:
            notes.append(affected_note)
        for test_path in affected:
            if test_path not in test_targets:
                test_targets.append(test_path)

    for extra in split_test_targets(extra_targets):
        if extra not in test_targets:
            test_targets.append(extra)
            notes.append(f"extra:{extra}")

    # Cap explosion
    if len(test_targets) > _MAX_TEST_TARGETS:
        notes.append(f"truncated_tests:{len(test_targets)}->{_MAX_TEST_TARGETS}")
        test_targets = test_targets[:_MAX_TEST_TARGETS]

    parallel_safe = [t for t in test_targets if not is_serial_preferred_target(t)]
    serial_preferred = [t for t in test_targets if is_serial_preferred_target(t)]

    if not test_targets:
        notes.append("no_tests_found: add extra_targets or run broader suite")

    notes.append("heuristic")
    return json.dumps(
        {
            "success": True,
            "changed_paths": changed,
            "lint_paths": lint_paths,
            "test_targets": test_targets,
            "parallel_safe": parallel_safe,
            "serial_preferred": serial_preferred,
            "run_tests_parallel_targets": " ".join(test_targets),
            "notes": notes,
            "hint": "下一步: lint(path=lint_paths) → run_tests_parallel(targets=run_tests_parallel_targets)",
        },
        ensure_ascii=False,
        indent=2,
    )


def _lint_candidates(repo_root: Path, path: str) -> list[str]:
    p = path.strip().lstrip("./")
    if not p:
        return []
    if p.endswith(".py"):
        abs_path = repo_root / p
        if abs_path.is_file():
            return [p]
        return [p]  # still suggest; lint will report missing
    # Directory of python package: allow linting the dir if it exists
    abs_path = repo_root / p
    if abs_path.is_dir() and any(abs_path.rglob("*.py")):
        return [p]
    return []


def _heuristic_tests_for_path(repo_root: Path, path: str) -> list[str]:
    p = path.strip().lstrip("./").replace("\\", "/")
    if not p:
        return []
    found: list[str] = []

    # Already a test file
    name = Path(p).name
    if name.startswith("test_") and name.endswith(".py"):
        return [p]
    if "/tests/" in f"/{p}/" and name.endswith(".py"):
        return [p]
    if p.startswith("dev_toolkit/test_") and p.endswith(".py"):
        return [p]

    # dev_toolkit/foo.py → dev_toolkit/test_foo.py；无孪生时按文件名 token / import 软匹配
    if p.startswith("dev_toolkit/") and p.endswith(".py") and not name.startswith("test_"):
        candidate = f"dev_toolkit/test_{name}"
        if (repo_root / candidate).is_file():
            found.append(candidate)
            return found
        stem = Path(name).stem  # e.g. code_tools
        toolkit_dir = repo_root / "dev_toolkit"
        if toolkit_dir.is_dir():
            soft: list[str] = []
            for tp in sorted(toolkit_dir.glob("test_*.py")):
                rel = f"dev_toolkit/{tp.name}"
                tp_stem = tp.stem
                # Prefer exact twin-style stems: test_<stem> already handled above.
                # Name-level only when module stem is a whole underscore token sequence,
                # never raw substring (code_tools ⊂ test_opencode_tools).
                if tp_stem == f"test_{stem}" or tp_stem.endswith(f"_{stem}"):
                    if rel not in soft:
                        soft.append(rel)
                    continue
                # import-based: test_speed_tools imports code_tools etc.
                try:
                    head = tp.read_text(encoding="utf-8", errors="ignore")[:12000]
                except OSError:
                    continue
                if re.search(rf"(?<![\w.]){re.escape(stem)}(?![\w])", head):
                    if rel not in soft:
                        soft.append(rel)
            found.extend(soft[:6])
        return found

    # modules/{key}/... → module tests / sandbox (capped)
    m = re.match(r"^modules/([^/]+)/", p)
    if m:
        module_key = m.group(1)
        module_root = repo_root / "modules" / module_key
        if module_root.is_dir():
            tests = sorted(module_root.rglob("test_*.py"))
            for tp in tests[:_MAX_MODULE_TESTS]:
                try:
                    found.append(str(tp.relative_to(repo_root)))
                except ValueError:
                    continue
            sandbox = module_root / "sandbox"
            if sandbox.is_dir() and str(sandbox.relative_to(repo_root)) not in found:
                # Prefer concrete test files over bare sandbox dir
                sandbox_tests = sorted(sandbox.rglob("test_*.py"))
                for tp in sandbox_tests[:6]:
                    rel = str(tp.relative_to(repo_root))
                    if rel not in found:
                        found.append(rel)
        return found

    # backend/app/.../x.py → backend/tests/**/test_*x*
    if p.startswith("backend/") and p.endswith(".py"):
        stem = Path(p).stem
        if stem.startswith("test_"):
            return [p]
        tests_root = repo_root / "backend" / "tests"
        if tests_root.is_dir():
            # exact-ish name matches first
            exact = list(tests_root.rglob(f"test_{stem}.py"))
            for tp in exact[:5]:
                found.append(str(tp.relative_to(repo_root)))
            if not found:
                # soft match containing stem
                soft = [tp for tp in tests_root.rglob("test_*.py") if stem in tp.stem][:5]
                for tp in soft:
                    rel = str(tp.relative_to(repo_root))
                    if rel not in found:
                        found.append(rel)
        return found

    # frontend: no default pytest
    if p.startswith("frontend/"):
        return []

    return found


async def _codegraph_affected(
    repo_root: Path,
    codegraph_cli: str,
    changed: list[str],
) -> tuple[list[str], str]:
    """Best-effort: codegraph affected <paths> → test files.

    CodeGraph 1.5+ default test globs miss monorepo layouts like
    ``dev_toolkit/test_*.py``; pass ``--filter **/test_*.py`` so toolkit
    and module-local tests are included.
    """
    # Only pass existing source-like paths to keep CLI happy
    paths = []
    for item in changed[:20]:
        if item.endswith((".py", ".ts", ".tsx", ".js", ".vue")):
            if (repo_root / item).exists():
                paths.append(item)
    if not paths:
        return [], ""

    # Prefer filtered JSON first (1.5+ monorepo-friendly), then unfiltered, then text.
    attempt_cmds: list[list[str]] = [
        [codegraph_cli, "affected", *paths, "--filter", "**/test_*.py", "-j"],
        [codegraph_cli, "affected", *paths, "--json"],
        [codegraph_cli, "affected", *paths, "--filter", "**/test_*.py", "--quiet"],
        [codegraph_cli, "affected", *paths, "--quiet"],
    ]

    last_err = ""
    text = ""
    used_cmd: list[str] = []
    for cmd in attempt_cmds:
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(repo_root),
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=20)
        except FileNotFoundError:
            return [], "codegraph_missing"
        except asyncio.TimeoutError:
            return [], "codegraph_affected_timeout"
        except Exception as exc:  # noqa: BLE001
            return [], f"codegraph_affected_error:{exc}"

        if proc.returncode != 0:
            last_err = (stderr or b"").decode("utf-8", errors="replace")[:200]
            continue
        candidate = (stdout or b"").decode("utf-8", errors="replace").strip()
        if not candidate:
            continue
        # Prefer a payload that already contains tests when JSON
        if candidate.lstrip().startswith("{"):
            try:
                data = json.loads(candidate)
                preview = _extract_test_paths_from_json(data, repo_root)
                if preview:
                    text = candidate
                    used_cmd = cmd
                    break
                # keep first JSON even if empty; later quiet/filter may fill
                if not text:
                    text = candidate
                    used_cmd = cmd
                continue
            except json.JSONDecodeError:
                pass
        text = candidate
        used_cmd = cmd
        break

    if not text:
        if last_err:
            return [], f"codegraph_affected_failed:{last_err}"
        return [], "codegraph_affected_empty"

    tests: list[str] = []
    try:
        data = json.loads(text)
        tests.extend(_extract_test_paths_from_json(data, repo_root))
    except json.JSONDecodeError:
        for line in text.splitlines():
            line = line.strip().strip('"').strip(",")
            if not line:
                continue
            if "test_" in line and line.endswith(".py"):
                m = re.search(r"((?:backend/|dev_toolkit/|modules/)[^\s:]+\.py)", line)
                candidate = m.group(1) if m else line
                candidate = candidate.lstrip("./")
                if (repo_root / candidate).is_file() and candidate not in tests:
                    tests.append(candidate)

    # Only keep tests that share a top-level package with the changed paths
    # (avoids unrelated codegraph noise like backend tests for pure toolkit edits).
    allowed_prefixes = _related_test_prefixes(changed)
    filtered = [t for t in tests if _path_matches_prefixes(t, allowed_prefixes)]
    filter_note = "filter:**/test_*.py" if any("--filter" in c for c in used_cmd) else "filter:default"
    if filtered:
        return filtered[:_MAX_TEST_TARGETS], f"codegraph_affected={len(filtered)} ({filter_note})"
    if tests:
        return [], f"codegraph_affected_filtered_out:{len(tests)} ({filter_note})"
    return [], f"codegraph_affected_no_tests ({filter_note})"


def _related_test_prefixes(changed: list[str]) -> list[str]:
    prefixes: list[str] = []
    for path in changed:
        p = path.strip().lstrip("./").replace("\\", "/")
        if p.startswith("dev_toolkit/"):
            if "dev_toolkit/" not in prefixes:
                prefixes.append("dev_toolkit/")
        elif p.startswith("modules/"):
            parts = p.split("/")
            if len(parts) >= 2:
                pref = f"modules/{parts[1]}/"
                if pref not in prefixes:
                    prefixes.append(pref)
        elif p.startswith("backend/"):
            if "backend/" not in prefixes:
                prefixes.append("backend/")
        elif p.startswith("frontend/"):
            if "frontend/" not in prefixes:
                prefixes.append("frontend/")
    return prefixes


def _path_matches_prefixes(path: str, prefixes: list[str]) -> bool:
    if not prefixes:
        return True
    p = path.strip().lstrip("./").replace("\\", "/")
    return any(p.startswith(pref) for pref in prefixes)


def _extract_test_paths_from_json(data: Any, repo_root: Path) -> list[str]:
    """Parse codegraph affected JSON (1.0 / 1.5 schemas)."""
    found: list[str] = []

    def _add(path: str) -> None:
        s = path.strip().strip('"').lstrip("./")
        if not s.endswith(".py"):
            return
        name = Path(s).name
        if not (name.startswith("test_") or "/tests/" in f"/{s}/" or name.endswith("_test.py")):
            return
        if (repo_root / s).is_file() and s not in found:
            found.append(s)

    # CodeGraph 1.5: {"changedFiles":[...], "affectedTests":[...]}
    if isinstance(data, dict):
        for key in ("affectedTests", "tests", "affected_tests"):
            raw = data.get(key)
            if isinstance(raw, list):
                for item in raw:
                    if isinstance(item, str):
                        _add(item)
                    elif isinstance(item, dict):
                        for k in ("path", "file", "test"):
                            if isinstance(item.get(k), str):
                                _add(item[k])
        if found:
            return found

    def walk(node: Any) -> None:
        if isinstance(node, str):
            _add(node)
            return
        if isinstance(node, list):
            for item in node:
                walk(item)
            return
        if isinstance(node, dict):
            for key, value in node.items():
                if key in {
                    "path",
                    "file",
                    "test",
                    "tests",
                    "affected",
                    "affectedTests",
                    "affected_tests",
                } or isinstance(value, (list, dict, str)):
                    walk(value)

    walk(data)
    return found
