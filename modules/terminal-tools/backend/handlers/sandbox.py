"""Workspace isolation, dangerous command detection, sandbox profile, safe env.

Shared by all terminal-tools capabilities.
"""

from __future__ import annotations

import logging
import os
import shutil
import sys
from pathlib import Path

from app.config import get_settings
from app.core.command_safety import check_dangerous_command as _check_dangerous_command
from app.core.workspace_security import (
    resolve_workspace_path as _resolve_workspace_path,
    ensure_user_workspace as _user_workspace,
)
from app.services.file_reader import resolve_caller_user_id

logger = logging.getLogger("v2.terminal-tools")

# ── Workspace configuration ─────────────────────────────────────────────
_WORKSPACE_ROOT = None
_MAX_OUTPUT_BYTES = 1 * 1024 * 1024   # 1 MB
_DEFAULT_TIMEOUT = 60                  # seconds


def _get_workspace_base() -> Path:
    """Return the root of all user workspaces (backend/data/workspaces/)."""
    global _WORKSPACE_ROOT
    if _WORKSPACE_ROOT is None:
        settings = get_settings()
        base = Path(settings.UPLOAD_DIR).resolve().parent
        _WORKSPACE_ROOT = (base / "workspaces").resolve()
        _WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)
    return _WORKSPACE_ROOT


def _resolve_user_id(caller: str) -> int:
    """Compatibility wrapper for older handlers."""
    return resolve_caller_user_id(caller)


# _user_workspace and _resolve_workspace_path are imported from app.core.workspace_security
# _check_dangerous_command is imported from app.core.command_safety


def _check_path_escape(command: str, workspace_real: str) -> str | None:
    """Check if command tries to access filesystem paths outside the workspace."""
    import shlex

    try:
        tokens = shlex.split(command)
    except ValueError:
        return None

    if not tokens:
        return None

    cmd_name = tokens[0]
    args = tokens[1:]

    TRAVERSAL_CMDS = frozenset({
        'cd', 'ls', 'find', 'tree', 'cat', 'less', 'more',
        'head', 'tail', 'nl', 'wc', 'stat', 'du', 'file',
        'readlink', 'realpath', 'dirname',
    })

    if cmd_name not in TRAVERSAL_CMDS:
        return None

    for arg in args:
        if arg.startswith('-') or arg in {'&&', '||', ';', '|', '>', '>>', '<'}:
            continue
        if arg == '~' or arg.startswith('~/'):
            return (f"Path escape blocked: '{arg}' expands to"
                    " home directory outside workspace")
        try:
            resolved = os.path.realpath(os.path.join(workspace_real, arg))
        except (OSError, ValueError):
            continue

        resolved_str = str(resolved)
        ws_prefix = workspace_real.rstrip('/') + '/'
        if not resolved_str.startswith(ws_prefix) and resolved_str != workspace_real:
            return (f"Path escape blocked: '{arg}' resolves to"
                    f" {resolved_str} outside workspace")

    return None


# ── macOS sandbox-exec profile ────────────────────────────────────────

_PY_PREFIX = os.path.realpath(sys.prefix)
_PY_BASE_PREFIX = os.path.realpath(sys.base_prefix)


def _build_sandbox_profile(workspace_real: str) -> str:
    """Return a sandbox-exec profile string that locks the child process to
    read-only system + full read/write of the workspace.
    """
    return f"""(version 1)
(import "system.sb")
(allow process-fork)
(allow process-exec)
(allow network*)
(allow mach-lookup)
(allow sysctl-read)
; metadata for path resolution (cd, ls, stat — no content)
(allow file-read-metadata)
; system tool/library dirs needed for binary and dynamic linker
(allow file-read*
  (subpath "/usr") (subpath "/bin") (subpath "/sbin")
  (subpath "/System") (subpath "/Library") (subpath "/opt/homebrew")
  (subpath "/private/var/db/dyld") (subpath "/private/var/folders")
  (subpath "/private/var/select") (subpath "/dev")
  (subpath "/private/etc/ssl")
  ; Python 解释器自身的 prefix（venv + base），run_python 需读 site-packages 才能启动；
  ; 只读、限定到解释器目录，不放开整个 /Users
  (subpath "{_PY_PREFIX}") (subpath "{_PY_BASE_PREFIX}")
  (literal "/private/etc/hosts") (literal "/private/etc/resolv.conf"))
; workspace — kernel-gated: nothing outside this subpath can be read or written
(allow file-read* file-write* (subpath "{workspace_real}"))
"""


# ── Minimal environment for child processes ───────────────────────────

def _safe_env(workspace: str) -> dict[str, str]:
    """Return a minimal whitelist of env vars for exec'd processes.

    We DO NOT forward the host os.environ wholesale — that leaks
    API keys, secrets, JWT tokens, and other sensitive values.
    """
    return {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": workspace,
        "WORKSPACE": workspace,
        "LANG": os.environ.get("LANG", "en_US.UTF-8"),
        "LC_ALL": os.environ.get("LC_ALL", "en_US.UTF-8"),
        "TMPDIR": os.environ.get("TMPDIR", "/tmp"),
    }
