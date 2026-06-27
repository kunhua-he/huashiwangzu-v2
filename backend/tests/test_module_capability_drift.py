import subprocess
import sys
from pathlib import Path


def test_module_manifest_public_actions_match_runtime_registrations():
    repo_root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [sys.executable, "scripts/check-capability-drift.py"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=15,
    )

    assert result.returncode == 0, result.stdout + result.stderr
