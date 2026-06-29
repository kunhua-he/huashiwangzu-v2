"""Multi-worker / concurrent file write resilience tests for Agent engine.

These tests verify that file-based persistence (atomic writes via temp+rename)
survives concurrent write contention without data loss or corruption.

Each test simulates N concurrent writers to a temp directory, then validates
that the target file is valid JSON and contains all expected records.

This complements ``test_agent_regression.py`` which tests structural contracts.
"""

import sys
import tempfile
import threading
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from modules.agent.backend.engine.file_state_lock import update_json_locked


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
                def _mutate(state: dict) -> dict:
                    rounds = state.setdefault("rounds", {})
                    rounds[f"conv_{worker_id}"] = [
                        {
                            "turn_index": 0,
                            "token_count_before": 100,
                            "token_count_after": 200,
                            "net_gain_tokens": 100,
                        }
                    ]
                    return state

                update_json_locked(target_file, {"rounds": {}}, _mutate)
            except Exception as e:
                with lock:
                    errors.append(f"Worker {worker_id}: {e}")

        threads = [threading.Thread(target=_writer, args=(i,)) for i in range(n_writers)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Write errors: {errors}"
        import json
        data = json.loads(target_file.read_text(encoding="utf-8"))
        assert isinstance(data, dict), "File must be valid JSON dict"
        assert "rounds" in data, "File must contain 'rounds' key"
        assert set(data["rounds"].keys()) == {f"conv_{i}" for i in range(n_writers)}

    def test_stuck_detector_concurrent_writes(self, _temp_dir: Path):
        target_file = _temp_dir / "stuck_rounds.json"

        n_writers = 20
        errors: list[str] = []

        def _writer(i: int):
            try:
                def _mutate(state: dict) -> dict:
                    state[f"session_{i}"] = [{"tool_name": "test", "is_empty": False}]
                    return state

                update_json_locked(target_file, {}, _mutate)
            except Exception as e:
                errors.append(f"Writer {i}: {e}")

        threads = [threading.Thread(target=_writer, args=(i,)) for i in range(n_writers)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Write errors: {errors}"
        import json
        data = json.loads(target_file.read_text(encoding="utf-8"))
        assert isinstance(data, dict)
        assert set(data.keys()) == {f"session_{i}" for i in range(n_writers)}
