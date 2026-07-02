"""Tests for release_gate.py — check level classification logic."""
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from dev_toolkit import release_gate  # noqa: E402

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
        assert "ALL CHECKS PASS" in output or "No BLOCKER" in output or "PASS_WITH_DEBT" in output


def test_output_contains_levels() -> None:
    """Each check should have a PASS/BLOCKER/DEBT/SKIPPED level."""
    r = _run(["--skip-ui"])
    for level in ("PASS", "BLOCKER", "DEBT", "SKIPPED_WITH_REASON"):
        if level in r.stdout:
            return
    # At least one of these should be present
    assert False, f"no expected level found in output: {r.stdout[:500]}"


def test_final_verdict_distinguishes_clean_pass_from_debt() -> None:
    original = list(release_gate.results)
    try:
        release_gate.results[:] = [{"check": "clean", "level": "PASS", "detail": "ok"}]
        assert release_gate.get_final_verdict() == "PASS"

        release_gate.results[:] = [{"check": "debt", "level": "DEBT", "detail": "tracked"}]
        assert release_gate.get_final_verdict() == "PASS_WITH_DEBT"

        release_gate.results[:] = [{"check": "skip", "level": "SKIPPED_WITH_REASON", "detail": "skipped"}]
        assert release_gate.get_final_verdict() == "PASS_WITH_DEBT"

        release_gate.results[:] = [{"check": "blocker", "level": "BLOCKER", "detail": "bad"}]
        assert release_gate.get_final_verdict() == "BLOCKER"
    finally:
        release_gate.results[:] = original


def test_sandbox_matrix_skips_are_debt_not_clean_pass() -> None:
    level, detail = release_gate.classify_sandbox_matrix(
        [{"module": "agent", "check": "pass"}, {"module": "missing-tests", "check": "skip"}],
        elapsed=1.2,
    )
    assert level == "DEBT"
    assert "skip" in detail


def test_parse_prefixed_json_extracts_machine_summary() -> None:
    output = 'noise\nRELEASE_GATE_JSON: {"verdict": "PASS_WITH_DEBT", "has_debt": true}\n'
    assert release_gate.parse_prefixed_json(output, "RELEASE_GATE_JSON:") == {
        "verdict": "PASS_WITH_DEBT",
        "has_debt": True,
    }


if __name__ == "__main__":
    test_help_output()
    test_release_gate_runs_with_skip_ui()
    test_output_contains_levels()
    test_final_verdict_distinguishes_clean_pass_from_debt()
    test_sandbox_matrix_skips_are_debt_not_clean_pass()
    test_parse_prefixed_json_extracts_machine_summary()
    print("\nAll release gate tests PASS")
