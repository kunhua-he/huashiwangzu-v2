"""Unified failure diagnostic recording for Agent engine.

Records structured failure events to ``data/agent/failure_diagnostics.jsonl``
(JSONL format, append-only) so that all exception degradation paths have a
queryable audit trail.

Constants:
    _DIAGNOSTIC_FILE: Path to the JSONL diagnostics file.
    _DIAGNOSTIC_MAX_BYTES: Max file size before trimming oldest 50% of records.
"""

import json
import logging
import os
import time
from pathlib import Path

logger = logging.getLogger("v2.agent").getChild("engine.failure_diagnostics")

_DIAGNOSTIC_FILE = "data/agent/failure_diagnostics.jsonl"
_DIAGNOSTIC_MAX_BYTES = 524288  # 512 KB


def record_failure(
    source: str,
    operation: str,
    error_type: str,
    error_message: str,
    conversation_id: int | None = None,
    extra: dict | None = None,
) -> None:
    """Append a structured failure diagnostic record.

    Args:
        source: Origin label (e.g. ``"hook"``, ``"chat"``, ``"memory"``).
        operation: What was being done (e.g. ``"run_hook"``, ``"write_recall_quality"``).
        error_type: Exception type name.
        error_message: Human-readable error description.
        conversation_id: Optional conversation context.
        extra: Optional additional structured data.
    """
    record = {
        "timestamp": time.time(),
        "source": source,
        "operation": operation,
        "error_type": error_type,
        "error_message": str(error_message)[:500],
        "conversation_id": conversation_id,
        "extra": extra or {},
    }
    path = Path(_DIAGNOSTIC_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        _trim_diagnostic_file(path)
        with open(str(path), "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())
    except OSError as exc:
        logger.warning("Failed to write diagnostic record: %s", exc)


def read_failure_diagnostics(limit: int = 50) -> list[dict]:
    """Read the most recent N diagnostic records.

    Args:
        limit: Maximum number of records to return (newest first).

    Returns:
        List of diagnostic dicts in reverse chronological order.
    """
    path = Path(_DIAGNOSTIC_FILE)
    if not path.exists():
        return []
    records: list[dict] = []
    try:
        raw = path.read_text(encoding="utf-8")
        for line in raw.strip().split("\n"):
            if line.strip():
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return []
    return records[-limit:][::-1]


def _trim_diagnostic_file(path: Path) -> None:
    """If the diagnostics file exceeds max bytes, keep only the newest 50% of lines."""
    try:
        size = path.stat().st_size
    except OSError:
        return
    if size < _DIAGNOSTIC_MAX_BYTES:
        return
    try:
        raw = path.read_text(encoding="utf-8")
        lines = raw.strip().split("\n")
        keep_count = max(len(lines) // 2, 1)
        kept = lines[-keep_count:]
        path.write_text("\n".join(kept) + "\n", encoding="utf-8")
    except OSError as exc:
        logger.warning("Failed to trim diagnostics file: %s", exc)
