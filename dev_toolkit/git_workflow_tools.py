"""Git workflow tools for repeatable local-to-main sync operations."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

TOOL_NAMES = {"git_sync_plan", "git_sync_workflow"}

_SAFE_BRANCH_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")


class GitWorkflowError(RuntimeError):
    def __init__(self, message: str, *, result: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.result = result or {}


async def _run_git(
    run_command_json,
    repo_root: Path,
    args: list[str],
    *,
    timeout: int = 120,
    check: bool = True,
) -> dict[str, Any]:
    result = await run_command_json(["git", *args], cwd=repo_root, timeout=timeout)
    if check and not result.get("success"):
        raise GitWorkflowError(
            f"git {' '.join(args)} failed",
            result=result,
        )
    return result


def _short_output(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "command": result.get("command"),
        "success": bool(result.get("success")),
        "returncode": result.get("returncode"),
        "duration_seconds": result.get("duration_seconds"),
        "stdout_tail": result.get("stdout_tail", result.get("stdout", ""))[-4000:],
        "stderr_tail": result.get("stderr_tail", result.get("stderr", ""))[-4000:],
    }


def _parse_status(stdout: str) -> tuple[str, str, list[dict[str, str]]]:
    lines = [line for line in stdout.splitlines() if line.strip()]
    branch_line = lines[0].removeprefix("## ").strip() if lines else ""
    current_branch = branch_line.split("...", 1)[0].strip()
    if current_branch.startswith("HEAD "):
        current_branch = "HEAD"
    entries: list[dict[str, str]] = []
    for line in lines[1:]:
        if len(line) < 4:
            continue
        path = line[3:].strip()
        if " -> " in path:
            path = path.rsplit(" -> ", 1)[1]
        entries.append({"status": line[:2].strip(), "path": path})
    return branch_line, current_branch, entries


def _validate_branch_name(branch: str) -> None:
    if not branch:
        raise GitWorkflowError("branch name is required")
    if (
        not _SAFE_BRANCH_RE.match(branch)
        or ".." in branch
        or branch.endswith(("/", ".lock", "."))
        or "/." in branch
        or branch.startswith("-")
    ):
        raise GitWorkflowError(f"unsafe branch name: {branch}")


def _suggest_branch_name(prefix: str = "codex/local-sync") -> str:
    safe_prefix = prefix.strip().strip("/") or "codex/local-sync"
    _validate_branch_name(safe_prefix + "-probe")
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"{safe_prefix}-{stamp}"


async def _branch_exists(run_command_json, repo_root: Path, branch: str) -> bool:
    result = await _run_git(
        run_command_json,
        repo_root,
        ["rev-parse", "--verify", "--quiet", branch],
        timeout=10,
        check=False,
    )
    return bool(result.get("success"))


async def git_sync_plan(
    run_command_json,
    repo_root: Path,
    *,
    target_branch: str = "main",
    remote: str = "origin",
    branch_prefix: str = "codex/local-sync",
) -> str:
    _validate_branch_name(target_branch)
    if not remote or remote.startswith("-"):
        raise GitWorkflowError(f"unsafe remote name: {remote}")

    status_result = await _run_git(
        run_command_json,
        repo_root,
        ["-c", "core.quotePath=false", "status", "--short", "--branch", "--untracked-files=all"],
        timeout=10,
    )
    branch_line, current_branch, entries = _parse_status(status_result.get("stdout", ""))
    head_result = await _run_git(run_command_json, repo_root, ["rev-parse", "--short", "HEAD"], timeout=10)
    remote_result = await _run_git(run_command_json, repo_root, ["remote", "get-url", remote], timeout=10, check=False)

    suggested_branch = _suggest_branch_name(branch_prefix)
    actions: list[str] = []
    if entries:
        if current_branch == target_branch:
            actions.append(f"create branch {suggested_branch} from {target_branch}")
        else:
            actions.append(f"use current branch {current_branch} as sync branch")
        actions.extend([
            "stage all local changes",
            "commit local changes",
            f"push sync branch to {remote}",
            f"fetch {remote}",
            f"fast-forward {target_branch}",
            f"push {target_branch} to {remote}",
        ])
    else:
        actions.append("no local changes to commit")

    payload = {
        "success": True,
        "mode": "local_as_source",
        "target_branch": target_branch,
        "remote": remote,
        "remote_url": remote_result.get("stdout", "").strip(),
        "current_branch": current_branch,
        "branch_line": branch_line,
        "head": head_result.get("stdout", "").strip(),
        "dirty_count": len(entries),
        "dirty_entries": entries[:200],
        "suggested_branch": suggested_branch,
        "will_end_on": target_branch if entries else current_branch,
        "actions": actions,
        "safety": {
            "merge": "ff-only",
            "force_push": False,
            "reset_hard": False,
            "rebase": False,
        },
        "verification": {
            "default": "git show --check --pretty=format: HEAD after commit",
            "stops_before_push_on_failure": True,
        },
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


async def git_sync_workflow(
    run_command_json,
    repo_root: Path,
    *,
    target_branch: str = "main",
    remote: str = "origin",
    branch_name: str = "",
    branch_prefix: str = "codex/local-sync",
    commit_message: str = "feat: sync local workflow updates",
    run_verification: bool = True,
    push_branch: bool = True,
    merge_to_target: bool = True,
    push_target: bool = True,
) -> str:
    _validate_branch_name(target_branch)
    if branch_name:
        _validate_branch_name(branch_name)
    if not remote or remote.startswith("-"):
        raise GitWorkflowError(f"unsafe remote name: {remote}")
    if not commit_message.strip():
        raise GitWorkflowError("commit_message is required")

    operations: list[dict[str, Any]] = []

    async def run_step(label: str, args: list[str], *, timeout: int = 120) -> dict[str, Any]:
        result = await _run_git(run_command_json, repo_root, args, timeout=timeout)
        item = {"label": label, **_short_output(result)}
        operations.append(item)
        return result

    try:
        initial_status = await _run_git(
            run_command_json,
            repo_root,
            ["-c", "core.quotePath=false", "status", "--short", "--branch", "--untracked-files=all"],
            timeout=10,
        )
        branch_line, current_branch, entries = _parse_status(initial_status.get("stdout", ""))
        if not entries:
            return json.dumps(
                {
                    "success": True,
                    "changed": False,
                    "message": "working tree is clean; nothing to sync",
                    "current_branch": current_branch,
                    "branch_line": branch_line,
                },
                ensure_ascii=False,
                indent=2,
            )

        sync_branch = branch_name or (current_branch if current_branch != target_branch else _suggest_branch_name(branch_prefix))
        _validate_branch_name(sync_branch)

        if current_branch != sync_branch:
            exists = await _branch_exists(run_command_json, repo_root, sync_branch)
            if exists:
                await run_step("switch sync branch", ["switch", sync_branch], timeout=30)
            else:
                await run_step("create sync branch", ["switch", "-c", sync_branch], timeout=30)

        await run_step("stage all changes", ["add", "-A"], timeout=60)
        await run_step("commit local changes", ["commit", "-m", commit_message.strip()], timeout=120)

        if run_verification:
            await run_step("verify committed diff whitespace", ["show", "--check", "--pretty=format:", "HEAD"], timeout=60)

        if push_branch:
            await run_step("push sync branch", ["push", "-u", remote, sync_branch], timeout=180)

        if merge_to_target:
            await run_step("fetch remote", ["fetch", remote], timeout=180)
            await run_step("switch target branch", ["switch", target_branch], timeout=60)
            await run_step("fast-forward merge", ["merge", "--ff-only", sync_branch], timeout=120)
            if push_target:
                await run_step("push target branch", ["push", remote, target_branch], timeout=180)

        final_status = await _run_git(
            run_command_json,
            repo_root,
            ["status", "--short", "--branch"],
            timeout=10,
        )
        _, final_branch, final_entries = _parse_status(final_status.get("stdout", ""))
        head = await _run_git(run_command_json, repo_root, ["rev-parse", "--short", "HEAD"], timeout=10)
        payload = {
            "success": True,
            "changed": True,
            "sync_branch": sync_branch,
            "target_branch": target_branch,
            "remote": remote,
            "commit": head.get("stdout", "").strip(),
            "final_branch": final_branch,
            "final_dirty_count": len(final_entries),
            "operations": operations,
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)
    except GitWorkflowError as exc:
        payload = {
            "success": False,
            "error": str(exc),
            "failed_result": _short_output(exc.result) if exc.result else None,
            "operations": operations,
            "safety_note": "Workflow stopped without force-push, reset, or rebase.",
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)


def tool_definitions() -> list[Any]:
    from mcp.types import Tool

    return [
        Tool(
            name="git_sync_plan",
            description="只读规划 Git 同步流程：分析当前分支/脏改/远端，并给出本地为准的支线提交、推送、快进合并 main 步骤。",
            inputSchema={
                "type": "object",
                "properties": {
                    "target_branch": {"type": "string", "description": "目标主线分支", "default": "main"},
                    "remote": {"type": "string", "description": "远端名", "default": "origin"},
                    "branch_prefix": {"type": "string", "description": "自动支线名前缀", "default": "codex/local-sync"},
                },
            },
        ),
        Tool(
            name="git_sync_workflow",
            description="执行标准 Git 同步：本地改动建支线提交、验证、推支线、ff-only 合并到主线、推主线；不做 reset/rebase/强推。",
            inputSchema={
                "type": "object",
                "properties": {
                    "target_branch": {"type": "string", "description": "目标主线分支", "default": "main"},
                    "remote": {"type": "string", "description": "远端名", "default": "origin"},
                    "branch_name": {"type": "string", "description": "可选支线名；为空则自动生成或使用当前非主线分支", "default": ""},
                    "branch_prefix": {"type": "string", "description": "自动支线名前缀", "default": "codex/local-sync"},
                    "commit_message": {"type": "string", "description": "提交信息", "default": "feat: sync local workflow updates"},
                    "run_verification": {"type": "boolean", "description": "提交后运行 git show --check", "default": True},
                    "push_branch": {"type": "boolean", "description": "是否推送支线", "default": True},
                    "merge_to_target": {"type": "boolean", "description": "是否快进合并到目标主线", "default": True},
                    "push_target": {"type": "boolean", "description": "合并后是否推送目标主线", "default": True},
                },
            },
        ),
    ]


def handles_tool(name: str) -> bool:
    return name in TOOL_NAMES


async def handle_tool(run_command_json, repo_root: Path, name: str, arguments: dict[str, Any]) -> str:
    if name == "git_sync_plan":
        return await git_sync_plan(
            run_command_json,
            repo_root,
            target_branch=str(arguments.get("target_branch", "main")),
            remote=str(arguments.get("remote", "origin")),
            branch_prefix=str(arguments.get("branch_prefix", "codex/local-sync")),
        )
    if name == "git_sync_workflow":
        return await git_sync_workflow(
            run_command_json,
            repo_root,
            target_branch=str(arguments.get("target_branch", "main")),
            remote=str(arguments.get("remote", "origin")),
            branch_name=str(arguments.get("branch_name", "")),
            branch_prefix=str(arguments.get("branch_prefix", "codex/local-sync")),
            commit_message=str(arguments.get("commit_message", "feat: sync local workflow updates")),
            run_verification=bool(arguments.get("run_verification", True)),
            push_branch=bool(arguments.get("push_branch", True)),
            merge_to_target=bool(arguments.get("merge_to_target", True)),
            push_target=bool(arguments.get("push_target", True)),
        )
    raise ValueError(f"未知 Git 工作流工具: {name}")
