"""Tests for git workflow MCP helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import anyio

from dev_toolkit.git_workflow_tools import git_sync_plan, git_sync_workflow


class FakeGitRunner:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    async def __call__(self, cmd: list[str], *, cwd: Path, timeout: int = 120) -> dict[str, Any]:
        del cwd, timeout
        self.calls.append(cmd)
        args = cmd[1:]
        stdout = ""
        success = True
        returncode = 0

        if args[:5] == ["-c", "core.quotePath=false", "status", "--short", "--branch"]:
            stdout = "## main...origin/main\n M dev_toolkit/server.py\n?? dev_toolkit/git_workflow_tools.py\n"
        elif args == ["status", "--short", "--branch"]:
            stdout = "## main...origin/main\n"
        elif args == ["rev-parse", "--short", "HEAD"]:
            stdout = "abc1234\n"
        elif args == ["remote", "get-url", "origin"]:
            stdout = "https://github.com/example/repo.git\n"
        elif args[:3] == ["rev-parse", "--verify", "--quiet"]:
            success = False
            returncode = 1
        elif args in (
            ["switch", "-c", "codex/test-sync"],
            ["add", "-A"],
            ["commit", "-m", "feat: test sync"],
            ["show", "--check", "--pretty=format:", "HEAD"],
            ["push", "-u", "origin", "codex/test-sync"],
            ["fetch", "origin"],
            ["switch", "main"],
            ["merge", "--ff-only", "codex/test-sync"],
            ["push", "origin", "main"],
        ):
            stdout = "ok\n"
        else:
            success = False
            returncode = 2

        return {
            "success": success,
            "returncode": returncode,
            "command": cmd,
            "stdout": stdout,
            "stderr": "" if success else "unexpected command",
            "stdout_tail": stdout,
            "stderr_tail": "" if success else "unexpected command",
            "duration_seconds": 0.001,
        }


def test_git_sync_plan_is_read_only_and_reports_actions() -> None:
    runner = FakeGitRunner()

    async def run() -> dict[str, Any]:
        raw = await git_sync_plan(runner, Path("/repo"), target_branch="main", remote="origin")
        return json.loads(raw)

    data = anyio.run(run)

    assert data["success"] is True
    assert data["dirty_count"] == 2
    assert data["current_branch"] == "main"
    assert data["safety"]["merge"] == "ff-only"
    assert data["safety"]["force_push"] is False
    assert runner.calls == [
        ["git", "-c", "core.quotePath=false", "status", "--short", "--branch", "--untracked-files=all"],
        ["git", "rev-parse", "--short", "HEAD"],
        ["git", "remote", "get-url", "origin"],
    ]


def test_git_sync_workflow_runs_safe_standard_sequence() -> None:
    runner = FakeGitRunner()

    async def run() -> dict[str, Any]:
        raw = await git_sync_workflow(
            runner,
            Path("/repo"),
            target_branch="main",
            remote="origin",
            branch_name="codex/test-sync",
            commit_message="feat: test sync",
        )
        return json.loads(raw)

    data = anyio.run(run)

    assert data["success"] is True
    assert data["sync_branch"] == "codex/test-sync"
    assert data["target_branch"] == "main"
    assert data["final_dirty_count"] == 0
    assert [item["label"] for item in data["operations"]] == [
        "create sync branch",
        "stage all changes",
        "commit local changes",
        "verify committed diff whitespace",
        "push sync branch",
        "fetch remote",
        "switch target branch",
        "fast-forward merge",
        "push target branch",
    ]
    flattened = [" ".join(call) for call in runner.calls]
    assert not any("reset --hard" in call for call in flattened)
    assert not any("rebase" in call for call in flattened)
    assert not any("--force" in call for call in flattened)
    assert ["git", "merge", "--ff-only", "codex/test-sync"] in runner.calls


def test_git_sync_workflow_clean_tree_is_noop() -> None:
    async def fake_clean(cmd: list[str], *, cwd: Path, timeout: int = 120) -> dict[str, Any]:
        del cwd, timeout
        if cmd[1:6] == ["-c", "core.quotePath=false", "status", "--short", "--branch"]:
            stdout = "## main...origin/main\n"
        else:
            stdout = ""
        return {
            "success": True,
            "returncode": 0,
            "command": cmd,
            "stdout": stdout,
            "stderr": "",
            "stdout_tail": stdout,
            "stderr_tail": "",
            "duration_seconds": 0.001,
        }

    async def run() -> dict[str, Any]:
        raw = await git_sync_workflow(fake_clean, Path("/repo"))
        return json.loads(raw)

    data = anyio.run(run)

    assert data["success"] is True
    assert data["changed"] is False
    assert data["message"] == "working tree is clean; nothing to sync"
