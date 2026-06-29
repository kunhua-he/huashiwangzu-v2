"""Cross-worker JSON file state helpers.

Atomic replace prevents torn files, but not lost read-modify-write updates.
These helpers hold an OS file lock across read, mutation, and replace.
"""
from __future__ import annotations

import fcntl
import json
import os
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

T = TypeVar("T")


def read_json_locked(path: Path, default: T) -> T:
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_suffix(path.suffix + ".lock")
    with open(lock_path, "a+", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            if not path.exists():
                return default
            raw = path.read_text(encoding="utf-8")
            if not raw.strip():
                return default
            return json.loads(raw)
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def update_json_locked(path: Path, default: T, mutator: Callable[[T], T]) -> T:
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_suffix(path.suffix + ".lock")
    with open(lock_path, "a+", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        tmp_path = ""
        try:
            if path.exists():
                raw = path.read_text(encoding="utf-8")
                state = json.loads(raw) if raw.strip() else default
            else:
                state = default
            next_state = mutator(state)
            fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
            with os.fdopen(fd, "w", encoding="utf-8") as tmp_file:
                json.dump(next_state, tmp_file, ensure_ascii=False)
            os.replace(tmp_path, str(path))
            return next_state
        finally:
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except FileNotFoundError:
                    pass
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
