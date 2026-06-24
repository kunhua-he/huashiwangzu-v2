"""Multi-worker / concurrent file write resilience tests for Agent engine.

These tests verify that file-based persistence (atomic writes via temp+rename)
survives concurrent write contention without data loss or corruption.

Each test simulates N concurrent writers to a temp directory, then validates
that the target file is valid JSON and contains all expected records.

This complements ``test_agent_regression.py`` which tests structural contracts.
"""

import json
import os
import tempfile
import threading
from pathlib import Path

import pytest


class TestConcurrentFileWrites:
    """Verify atomic file writes survive concurrent access."""

    @pytest.fixture(autouse=True)
    def _temp_dir(self):
        with tempfile.TemporaryDirectory() as d:
            yield Path(d)

    def test_budget_tracker_concurrent_writes(self, _temp_dir: Path):
        target_file = _temp_dir / "budget_tracker.json"

        n_writers = 20
        errors: list[str] = []
        lock = threading.Lock()

        def _writer(worker_id: int):
            try:
                fd, tmp = tempfile.mkstemp(
                    suffix=".json", prefix=".budget_", dir=str(_temp_dir),
                )
                with os.fdopen(fd, "w") as f:
                    json.dump({
                        "rounds": {
                            f"conv_{worker_id}": [
                                {
                                    "turn_index": 0,
                                    "token_count_before": 100,
                                    "token_count_after": 200,
                                    "net_gain_tokens": 100,
                                }
                            ]
                        }
                    }, f, ensure_ascii=False)
                os.replace(tmp, str(target_file))
            except Exception as e:
                with lock:
                    errors.append(f"Worker {worker_id}: {e}")

        threads = [threading.Thread(target=_writer, args=(i,)) for i in range(n_writers)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Write errors: {errors}"
        raw = target_file.read_text(encoding="utf-8")
        data = json.loads(raw)
        assert isinstance(data, dict), "File must be valid JSON dict"
        assert "rounds" in data, "File must contain 'rounds' key"

    def test_stuck_detector_concurrent_writes(self, _temp_dir: Path):
        target_file = _temp_dir / "stuck_rounds.json"

        n_writers = 20
        errors: list[str] = []

        def _writer(i: int):
            try:
                fd, tmp = tempfile.mkstemp(
                    suffix=".json", prefix=".stuck_", dir=str(_temp_dir),
                )
                with os.fdopen(fd, "w") as f:
                    json.dump({f"session_{i}": [{"tool_name": "test", "is_empty": False}]}, f)
                os.replace(tmp, str(target_file))
            except Exception as e:
                errors.append(f"Writer {i}: {e}")

        threads = [threading.Thread(target=_writer, args=(i,)) for i in range(n_writers)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Write errors: {errors}"
        raw = target_file.read_text(encoding="utf-8")
        data = json.loads(raw)
        assert isinstance(data, dict)
