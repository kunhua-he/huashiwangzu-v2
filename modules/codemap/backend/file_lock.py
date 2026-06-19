"""File-based cross-worker lock service.

Uses JSON file persistence (locks.json) to ensure locks are shared across
all uvicorn workers. Atomic writes via temp file + rename.

Lock model:
  - acquire_lock(path, agent_id, ttl=600) -> {success: bool, error: str}
  - check_lock(path) -> {locked: bool, owner: str, remaining_ttl: float}
  - release_lock(path) -> {success: bool}
  - list_locks() -> {locks: [{path, agent_id, expires_at, remaining_ttl}]}
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
import time
from pathlib import Path

logger = logging.getLogger("v2.codemap.file_lock")

DATA_DIR = Path(__file__).resolve().parent / "data"
LOCK_FILE = DATA_DIR / "locks.json"
_LOCK_FILE_LOCK = threading.Lock()


def _ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _read_locks() -> dict:
    try:
        if LOCK_FILE.exists():
            with open(LOCK_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to read lock file, starting fresh: %s", exc)
    return {}


def _write_locks(locks: dict) -> bool:
    """Atomically write locks dict to file (temp + rename)."""
    try:
        _ensure_data_dir()
        fd, tmp_path = tempfile.mkstemp(dir=str(DATA_DIR), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(locks, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, str(LOCK_FILE))
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
        return True
    except OSError as exc:
        logger.error("Failed to write lock file: %s", exc)
        return False


def _expire_locks(locks: dict) -> None:
    """Remove expired locks in-place."""
    now = time.time()
    expired = [p for p, lk in locks.items() if lk.get("expires_at", 0) <= now]
    for p in expired:
        del locks[p]


def acquire_lock(path: str, agent_id: str, ttl: int = 600) -> dict:
    """Acquire a lock on *path* for *agent_id* with *ttl* seconds TTL."""
    expires_at = time.time() + ttl
    with _LOCK_FILE_LOCK:
        locks = _read_locks()
        _expire_locks(locks)
        existing = locks.get(path)
        if existing and existing.get("agent_id") != agent_id:
            remaining = existing["expires_at"] - time.time()
            return {
                "success": False,
                "error": f"Already locked by agent '{existing['agent_id']}' "
                         f"(remaining TTL: {max(0, round(remaining, 1))}s)",
            }
        locks[path] = {"agent_id": agent_id, "expires_at": expires_at}
        if not _write_locks(locks):
            return {"success": False, "error": "Failed to persist lock"}
    return {"success": True, "path": path, "agent_id": agent_id, "ttl": ttl}


def check_lock(path: str) -> dict:
    """Check if *path* is locked."""
    with _LOCK_FILE_LOCK:
        locks = _read_locks()
        _expire_locks(locks)
        lock = locks.get(path)
        if lock and lock.get("expires_at", 0) > time.time():
            remaining = lock["expires_at"] - time.time()
            return {"locked": True, "owner": lock.get("agent_id", ""),
                    "remaining_ttl": round(remaining, 1)}
    return {"locked": False, "owner": None, "remaining_ttl": 0.0}


def release_lock(path: str) -> dict:
    """Release the lock on *path*."""
    with _LOCK_FILE_LOCK:
        locks = _read_locks()
        if path not in locks:
            return {"success": False, "error": "No lock found for path"}
        del locks[path]
        if not _write_locks(locks):
            return {"success": False, "error": "Failed to persist lock release"}
    return {"success": True, "path": path}


def list_locks() -> dict:
    """List all active locks."""
    with _LOCK_FILE_LOCK:
        locks = _read_locks()
        _expire_locks(locks)
        now = time.time()
        result = [
            {"path": p, "agent_id": lk["agent_id"],
             "expires_at": lk["expires_at"],
             "remaining_ttl": max(0, round(lk["expires_at"] - now, 1))}
            for p, lk in locks.items()
            if lk.get("expires_at", 0) > now
        ]
    return {"locks": result, "count": len(result)}
