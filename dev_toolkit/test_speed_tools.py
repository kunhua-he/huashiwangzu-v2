"""Tests for parallel verify, select_verify, and rg_search speed tools."""

from __future__ import annotations

import json
from pathlib import Path

import anyio
import pytest

from dev_toolkit import code_tools, search_tools, verify_tools

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_split_test_targets_accepts_json_and_spaces() -> None:
    assert code_tools.split_test_targets("a.py b.py") == ["a.py", "b.py"]
    assert code_tools.split_test_targets('["a.py", "b.py"]') == ["a.py", "b.py"]
    assert code_tools.split_test_targets("a.py,\nb.py") == ["a.py", "b.py"]
    assert code_tools.split_test_targets(["a.py", "b.py"]) == ["a.py", "b.py"]


def test_split_path_list_accepts_native_list_and_python_repr() -> None:
    assert code_tools.split_path_list(["a.py", "b.py"]) == ["a.py", "b.py"]
    assert code_tools.split_path_list("['a.py', 'b.py']") == ["a.py", "b.py"]
    assert code_tools.split_path_list('["a.py", "b.py"]') == ["a.py", "b.py"]


def test_is_serial_preferred_target() -> None:
    assert code_tools.is_serial_preferred_target("backend/tests/test_e2e_foo.py") is True
    assert code_tools.is_serial_preferred_target("dev_toolkit/test_speed_tools.py") is False
    assert code_tools.is_serial_preferred_target("modules/x/live_check.py") is True


def test_run_tests_parallel_fans_out_and_aggregates() -> None:
    calls: list[dict] = []

    async def fake_run_command_json(cmd, *, cwd: Path, timeout: int = 120, env=None):
        calls.append({"cmd": cmd, "cwd": cwd, "timeout": timeout})
        target = " ".join(str(x) for x in cmd)
        ok = "fail_me" not in target
        return {
            "success": ok,
            "returncode": 0 if ok else 1,
            "stdout": "ok" if ok else "FAILED",
            "stderr": "",
            "duration_seconds": 0.05,
        }

    async def run() -> dict:
        raw = await code_tools.run_tests_parallel(
            fake_run_command_json,
            REPO_ROOT,
            targets="dev_toolkit/test_server_helpers.py dev_toolkit/test_speed_tools.py fail_me.py",
            max_workers=3,
            mode="force_parallel",
            timeout_per_target=30,
        )
        return json.loads(raw)

    data = anyio.run(run)
    assert data["total"] == 3
    assert data["parallel_count"] == 3
    assert data["serial_count"] == 0
    assert data["passed"] == 2
    assert data["failed"] == 1
    assert data["success"] is False
    assert "fail_me.py" in data["failed_targets"]
    assert len(calls) == 3


def test_run_tests_parallel_auto_puts_e2e_in_serial_bucket() -> None:
    order: list[str] = []

    async def fake_run_command_json(cmd, *, cwd: Path, timeout: int = 120, env=None):
        # last path-like arg
        label = str(cmd[-1])
        order.append(label)
        return {"success": True, "returncode": 0, "stdout": "ok", "stderr": "", "duration_seconds": 0.01}

    async def run() -> dict:
        raw = await code_tools.run_tests_parallel(
            fake_run_command_json,
            REPO_ROOT,
            targets="dev_toolkit/test_a.py backend/tests/test_e2e_foo.py",
            mode="auto",
            max_workers=2,
        )
        return json.loads(raw)

    data = anyio.run(run)
    assert data["parallel_count"] == 1
    assert data["serial_count"] == 1
    assert data["success"] is True
    # parallel first, then serial
    assert any("test_a" in x for x in order[:1]) or "test_a" in order[0]


def test_lint_accepts_directory_and_parallel_paths(tmp_path: Path) -> None:
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "a.py").write_text("x = 1\n", encoding="utf-8")
    (pkg / "b.py").write_text("y = 2\n", encoding="utf-8")
    # Use real repo ruff path simulation via fake
    calls: list[list[str]] = []

    async def fake_run_command_json(cmd, *, cwd: Path, timeout: int = 120, env=None):
        calls.append(list(cmd))
        return {"success": True, "returncode": 0, "stdout": "", "stderr": "", "duration_seconds": 0.01}

    async def run_dir() -> dict:
        raw = await code_tools.lint(fake_run_command_json, tmp_path, "ruff", "pkg", max_workers=2)
        return json.loads(raw)

    data = anyio.run(run_dir)
    assert data["success"] is True
    assert data.get("is_dir") is True
    assert len(calls) == 1
    assert calls[0][-1].endswith("pkg")

    calls.clear()

    async def run_multi() -> dict:
        raw = await code_tools.lint(
            fake_run_command_json,
            tmp_path,
            "ruff",
            "pkg/a.py,pkg/b.py",
            max_workers=2,
        )
        return json.loads(raw)

    multi = anyio.run(run_multi)
    assert multi["success"] is True
    assert multi["failed_count"] == 0
    assert multi["max_workers"] == 2
    assert len(calls) == 2


def test_select_verify_maps_dev_toolkit_twin() -> None:
    async def fake_run_command_json(cmd, *, cwd: Path, timeout: int = 120, env=None):
        return {"success": True, "stdout": "", "stderr": "", "returncode": 0}

    async def run() -> dict:
        raw = await verify_tools.select_verify(
            fake_run_command_json,
            REPO_ROOT,
            codegraph_cli="codegraph-not-used",
            paths="dev_toolkit/service_lifecycle_tools.py",
            from_git=False,
            include_codegraph_affected=False,
        )
        return json.loads(raw)

    data = anyio.run(run)
    assert data["success"] is True
    assert "dev_toolkit/service_lifecycle_tools.py" in data["lint_paths"]
    assert "dev_toolkit/test_service_lifecycle_tools.py" in data["test_targets"]
    assert "dev_toolkit/test_service_lifecycle_tools.py" in data["parallel_safe"]


def test_select_verify_accepts_native_list_and_soft_match() -> None:
    async def fake_run_command_json(cmd, *, cwd: Path, timeout: int = 120, env=None):
        return {"success": True, "stdout": "", "stderr": "", "returncode": 0}

    async def run() -> dict:
        raw = await verify_tools.select_verify(
            fake_run_command_json,
            REPO_ROOT,
            codegraph_cli="codegraph-not-used",
            paths=["dev_toolkit/code_tools.py", "dev_toolkit/search_tools.py"],
            from_git=False,
            include_codegraph_affected=False,
        )
        return json.loads(raw)

    data = anyio.run(run)
    assert data["success"] is True
    assert "dev_toolkit/code_tools.py" in data["lint_paths"]
    assert "dev_toolkit/search_tools.py" in data["lint_paths"]
    assert "dev_toolkit/test_speed_tools.py" in data["test_targets"]
    assert all(t.startswith("dev_toolkit/") for t in data["test_targets"])


def test_extract_test_paths_from_codegraph_1_5_schema() -> None:
    data = {
        "changedFiles": ["dev_toolkit/code_tools.py"],
        "affectedTests": [
            "dev_toolkit/test_speed_tools.py",
            "dev_toolkit/test_server_helpers.py",
            "not_a_test.py",
        ],
        "totalDependentsTraversed": 7,
    }
    found = verify_tools._extract_test_paths_from_json(data, REPO_ROOT)
    assert "dev_toolkit/test_speed_tools.py" in found
    assert "dev_toolkit/test_server_helpers.py" in found
    assert "not_a_test.py" not in found


def test_select_verify_with_extra_targets() -> None:
    async def fake_run_command_json(cmd, *, cwd: Path, timeout: int = 120, env=None):
        return {"success": True, "stdout": "", "stderr": "", "returncode": 0}

    async def run() -> dict:
        raw = await verify_tools.select_verify(
            fake_run_command_json,
            REPO_ROOT,
            paths="",
            extra_targets="dev_toolkit/test_speed_tools.py",
            include_codegraph_affected=False,
        )
        return json.loads(raw)

    data = anyio.run(run)
    assert data["success"] is True
    assert data["test_targets"] == ["dev_toolkit/test_speed_tools.py"]
    assert data["parallel_safe"] == ["dev_toolkit/test_speed_tools.py"]


def test_rg_search_finds_own_marker() -> None:
    marker = "RG_SEARCH_MARKER_SPEED_TOOLS_ZX9"

    async def run() -> dict:
        raw = await search_tools.rg_search(
            REPO_ROOT,
            pattern=marker,
            path="dev_toolkit",
            glob="test_speed_tools.py",
            max_matches=5,
        )
        return json.loads(raw)

    data = anyio.run(run)
    assert data["success"] is True
    assert data["match_count"] >= 1
    assert any(marker in m.get("text", "") for m in data["matches"])


def test_tool_definitions_include_new_tools() -> None:
    code_names = {t.name for t in code_tools.tool_definitions()}
    assert "run_tests_parallel" in code_names
    search_names = {t.name for t in search_tools.tool_definitions()}
    assert "rg_search" in search_names
    verify_names = {t.name for t in verify_tools.tool_definitions()}
    assert "select_verify" in verify_names


def test_server_version_bumped() -> None:
    from dev_toolkit.mcp_entry import SERVER_VERSION

    assert SERVER_VERSION == "1.1.0"
