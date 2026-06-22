"""Shell command execution capability for terminal-tools.

Capability: terminal-tools:exec — Run shell commands in user workspace.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys

from .sandbox import (
    _resolve_user_id,
    _user_workspace,
    _check_dangerous_command,
    _check_path_escape,
    _build_sandbox_profile,
    _safe_env,
    _DEFAULT_TIMEOUT,
    _MAX_OUTPUT_BYTES,
)

logger = logging.getLogger("v2.terminal-tools")


# ═══════════════════════════════════════════════════════════════════════
# Capability: terminal-tools:exec
# ═══════════════════════════════════════════════════════════════════════
async def _exec(params: dict, caller: str) -> dict:
    """Execute a shell command inside a kernel-level sandbox on macOS.

    On macOS: wraps the child in sandbox-exec — read-only system,
    read/write only the user workspace.  No amount of model cleverness
    can escape the kernel sandbox.

    On Linux (no sandbox-exec): fail-closed — exec is disabled.
    """
    user_id = _resolve_user_id(caller)
    workspace = _user_workspace(user_id)
    workspace_real = os.path.realpath(str(workspace))
    command = params.get("command", "").strip()
    timeout = int(params.get("timeout", _DEFAULT_TIMEOUT))

    if not command:
        return {"success": False, "error": "No command provided"}

    if timeout <= 0 or timeout > 600:
        timeout = _DEFAULT_TIMEOUT

    danger = _check_dangerous_command(command)
    if danger:
        logger.warning("user=%s blocked dangerous command: %s", user_id, command)
        return {"success": False, "error": danger, "command": command}

    escape = _check_path_escape(command, str(workspace_real))
    if escape:
        logger.warning("user=%s blocked path escape: %s", user_id, command)
        return {"success": False, "error": escape, "command": command}

    safe_env = _safe_env(str(workspace_real))

    if sys.platform == "darwin" and shutil.which("sandbox-exec"):
        profile = _build_sandbox_profile(workspace_real)
        argv = ["sandbox-exec", "-p", profile, "/bin/sh", "-c", command]
        cwd = workspace_real
    else:
        return {
            "success": False,
            "error": (
                "当前平台无可用沙盒(sandbox-exec/bwrap)，exec 已禁用。"
                "需要 macOS 或安装了 bubblewrap 的 Linux。"
            ),
            "command": command,
        }

    logger.info("user=%s exec(sandbox): %s", user_id, command[:200])

    try:
        proc = subprocess.run(
            argv, cwd=cwd, capture_output=True, text=True,
            timeout=timeout, env=safe_env,
        )
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": f"Command timed out after {timeout}s",
            "timed_out": True, "return_code": -1,
            "stdout": "", "stderr": f"Timeout after {timeout}s",
            "command": command,
        }
    except Exception as exc:
        return {
            "success": False,
            "error": f"Command execution failed: {exc}",
            "return_code": -1, "stdout": "", "stderr": str(exc),
            "command": command,
        }

    stdout = proc.stdout or ""
    stderr = proc.stderr or ""
    stdout_truncated = len(stdout) > _MAX_OUTPUT_BYTES
    stderr_truncated = len(stderr) > _MAX_OUTPUT_BYTES
    if stdout_truncated:
        stdout = stdout[:_MAX_OUTPUT_BYTES] + "\n... [stdout truncated at 1MB]"
    if stderr_truncated:
        stderr = stderr[:_MAX_OUTPUT_BYTES] + "\n... [stderr truncated at 1MB]"

    return {
        "success": proc.returncode == 0,
        "return_code": proc.returncode,
        "stdout": stdout, "stderr": stderr,
        "stdout_truncated": stdout_truncated,
        "stderr_truncated": stderr_truncated,
        "command": command,
    }
