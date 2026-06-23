"""Workspace security — per-user workspace directory management.

Ensures all user file operations are confined to their workspace directory
under backend/data/workspaces/{user_id}/.
"""

import logging
import os
from pathlib import Path

from app.config import get_settings
from app.core.path_security import validate_within_dir

logger = logging.getLogger("v2.workspace_security")

_WORKSPACE_ROOT: Path | None = None


def _get_workspace_base() -> Path:
    """Return the root of all user workspaces (backend/data/workspaces/)."""
    global _WORKSPACE_ROOT
    if _WORKSPACE_ROOT is None:
        settings = get_settings()
        base = Path(settings.UPLOAD_DIR).resolve().parent
        _WORKSPACE_ROOT = (base / "workspaces").resolve()
        _WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)
    return _WORKSPACE_ROOT


def ensure_user_workspace(user_id: int) -> Path:
    """Return and ensure the workspace directory for a given user."""
    ws = _get_workspace_base() / str(user_id)
    ws.mkdir(parents=True, exist_ok=True)
    return ws


def resolve_workspace_path(user_id: int, relative_path: str) -> Path:
    """Resolve a relative path within the user workspace.

    Returns the resolved Path if safe.
    Raises ValueError if the path escapes the workspace boundary.
    """
    workspace_root = ensure_user_workspace(user_id)
    cleaned = relative_path.strip()
    if not cleaned or cleaned == ".":
        return workspace_root

    target = (workspace_root / cleaned).resolve()
    validate_within_dir(target, workspace_root)
    return target
