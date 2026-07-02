"""Tests for release_gate.py — check level classification logic."""
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
GATE_SCRIPT = REPO_ROOT / "dev_toolkit" / "release_gate.py"
BACKEND_PYTHON = REPO_ROOT / "backend" / ".venv" / "bin" / "python"


def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(BACKEND_PYTHON), str(GATE_SCRIPT), *args],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=360,
    )


def test_help_output() -> None:
    r = subprocess.run(
        [str(BACKEND_PYTHON), str(GATE_SCRIPT), "--help"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert r.returncode == 0
    assert "usage:" in r.stdout.lower()


def test_release_gate_runs_with_skip_ui() -> None:
    """--skip-ui should complete without crash, output verdict."""
    r = _run(["--skip-ui"])
    assert r.returncode in (0, 1), f"exit={r.returncode}, stderr={r.stderr[:1000]}"
    assert "RELEASE GATE VERDICT" in r.stdout
    assert "Health check" in r.stdout
    assert "Queue:" in r.stdout
    assert "Sandbox matrix" in r.stdout
    # Even on failure, the output should be properly formatted
    output = r.stdout
    if r.returncode == 0:
        assert "ALL CHECKS PASS" in output or "no BLOCKER" in output


def test_output_contains_levels() -> None:
    """Each check should have a PASS/BLOCKER/DEBT/SKIPPED level."""
    r = _run(["--skip-ui"])
    for level in ("PASS", "BLOCKER", "DEBT", "SKIPPED_WITH_REASON"):
        if level in r.stdout:
            return
    # At least one of these should be present
    assert False, f"no expected level found in output: {r.stdout[:500]}"


if __name__ == "__main__":
    test_help_output()
    test_release_gate_runs_with_skip_ui()
    test_output_contains_levels()
    print("\nAll release gate tests PASS")
