"""File operation capabilities for terminal-tools.

Capabilities:
  terminal-tools:write_file   — Write files into user workspace
  terminal-tools:read_file    — Read files from user workspace
  terminal-tools:list_workspace — List files in user workspace
  terminal-tools:publish      — Publish workspace files to framework FS
  terminal-tools:import       — Import framework FS files into workspace
"""

from __future__ import annotations

import io
import logging
import os

from app.core.exceptions import NotFound, PermissionDenied

from .sandbox import (
    _resolve_user_id,
    _user_workspace,
    _resolve_workspace_path,
)

logger = logging.getLogger("v2.terminal-tools")


# ═══════════════════════════════════════════════════════════════════════
# Capability: terminal-tools:write_file
# ═══════════════════════════════════════════════════════════════════════
async def _write_file(params: dict, caller: str) -> dict:
    """Write content to a file in the user workspace."""
    user_id = _resolve_user_id(caller)
    path = params.get("path", "").strip()
    content = params.get("content", "")

    if not path:
        return {"success": False, "error": "No path provided"}

    try:
        target = _resolve_workspace_path(user_id, path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    except ValueError as exc:
        return {"success": False, "error": str(exc), "path": path}
    except Exception as exc:
        return {"success": False, "error": f"Write failed: {exc}", "path": path}

    return {
        "success": True,
        "path": str(target.relative_to(_user_workspace(user_id))),
        "absolute_path": str(target),
        "size": target.stat().st_size,
    }


# ═══════════════════════════════════════════════════════════════════════
# Capability: terminal-tools:read_file
# ═══════════════════════════════════════════════════════════════════════
async def _read_file(params: dict, caller: str) -> dict:
    """Read content from a file in the user workspace."""
    user_id = _resolve_user_id(caller)
    path = params.get("path", "").strip()

    if not path:
        return {"success": False, "error": "No path provided"}

    try:
        target = _resolve_workspace_path(user_id, path)
    except ValueError as exc:
        return {"success": False, "error": str(exc), "path": path}

    if not target.exists():
        return {"success": False, "error": f"File not found: {path}", "path": path}
    if not target.is_file():
        return {"success": False, "error": f"Not a file: {path}", "path": path}

    try:
        content = target.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raw = target.read_bytes()
        return {
            "success": True,
            "path": path,
            "size": len(raw),
            "binary": True,
            "content": None,
            "note": "Binary file — cannot display as text",
        }
    except Exception as exc:
        return {"success": False, "error": f"Read failed: {exc}", "path": path}

    return {
        "success": True,
        "path": path,
        "size": len(content),
        "content": content,
        "binary": False,
    }


# ═══════════════════════════════════════════════════════════════════════
# Capability: terminal-tools:list_workspace
# ═══════════════════════════════════════════════════════════════════════
async def _list_workspace(params: dict, caller: str) -> dict:
    """List files and directories in the user workspace."""
    user_id = _resolve_user_id(caller)
    path = params.get("path", "").strip() or "."

    try:
        target = _resolve_workspace_path(user_id, path)
    except ValueError as exc:
        return {"success": False, "error": str(exc), "path": path}

    if not target.exists():
        return {"success": False, "error": f"Path not found: {path}", "path": path}
    if not target.is_dir():
        return {"success": False, "error": f"Not a directory: {path}", "path": path}

    items = []
    try:
        with os.scandir(target) as entries:
            for entry in entries:
                stat = entry.stat()
                items.append({
                    "name": entry.name,
                    "is_dir": entry.is_dir(),
                    "is_file": entry.is_file(),
                    "size": stat.st_size if entry.is_file() else 0,
                    "modified_at": stat.st_mtime,
                })
    except Exception as exc:
        return {"success": False, "error": f"List failed: {exc}", "path": path}

    items.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))

    return {
        "success": True,
        "path": str(target.relative_to(_user_workspace(user_id))) if target != _user_workspace(user_id) else ".",
        "items": items,
        "count": len(items),
    }


# ═══════════════════════════════════════════════════════════════════════
# Capability: terminal-tools:publish
# ═══════════════════════════════════════════════════════════════════════
async def _publish(params: dict, caller: str) -> dict:
    """Publish a workspace file to the framework file system (desktop-visible)."""
    from app.services import file_upload_service

    user_id = _resolve_user_id(caller)
    path = params.get("path", "").strip()
    display_name = params.get("filename", "").strip()
    folder_id = int(params.get("folder_id", 0)) if params.get("folder_id") else None

    if not path:
        return {"success": False, "error": "No path provided"}

    try:
        source = _resolve_workspace_path(user_id, path)
    except ValueError as exc:
        return {"success": False, "error": str(exc), "path": path}

    if not source.exists():
        return {"success": False, "error": f"File not found: {path}", "path": path}
    if not source.is_file():
        return {"success": False, "error": f"Not a file: {path}", "path": path}

    try:
        file_bytes = source.read_bytes()
    except Exception as exc:
        return {"success": False, "error": f"Read failed: {exc}", "path": path}

    filename = display_name if display_name else source.name
    target_folder = folder_id if (folder_id and folder_id > 0) else None

    try:
        from app.database import AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            result = await file_upload_service.upload_file(
                db, io.BytesIO(file_bytes), filename, user_id, target_folder,
            )
    except Exception as exc:
        return {"success": False, "error": f"Publish failed: {exc}", "path": path}

    return {
        "success": True,
        "file_id": result["id"],
        "name": result["name"],
        "extension": result["extension"],
        "size": result["size"],
        "mime_type": result["mime_type"],
        "deduplicated": result.get("deduplicated", False),
        "source_path": path,
    }


# ═══════════════════════════════════════════════════════════════════════
# Capability: terminal-tools:import
# ═══════════════════════════════════════════════════════════════════════
async def _import(params: dict, caller: str) -> dict:
    """Import a framework file into the user workspace."""
    from app.services import file_service, file_preview_service

    user_id = _resolve_user_id(caller)
    file_id = int(params.get("file_id", 0))
    target_path = params.get("target_path", "").strip()

    if file_id <= 0:
        return {"success": False, "error": "file_id must be a positive integer"}

    from app.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        try:
            file_record = await file_service.check_file_access(db, file_id, user_id)
        except (NotFound, PermissionDenied):
            return {"success": False, "error": "File not found or access denied"}

        storage_path = file_preview_service._resolve_storage_path(file_record)
        if not storage_path:
            return {"success": False, "error": "File on disk not found — storage path invalid"}

        try:
            file_bytes = storage_path.read_bytes()
        except Exception as exc:
            return {"success": False, "error": f"Read disk file failed: {exc}"}

    if target_path:
        filename = target_path
    else:
        ext = file_record.extension
        filename = f"{file_record.name}.{ext}" if ext else file_record.name

    try:
        target = _resolve_workspace_path(user_id, filename)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(file_bytes)
    except ValueError as exc:
        return {"success": False, "error": str(exc), "path": filename}

    return {
        "success": True,
        "path": str(target.relative_to(_user_workspace(user_id))),
        "absolute_path": str(target),
        "size": target.stat().st_size,
        "source_file_id": file_id,
        "source_file_name": f"{file_record.name}.{file_record.extension}"
        if file_record.extension else file_record.name,
    }
