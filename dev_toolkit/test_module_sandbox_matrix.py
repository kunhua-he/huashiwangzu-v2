"""Tests for module_sandbox_matrix.py."""
import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MATRIX_SCRIPT = REPO_ROOT / "dev_toolkit" / "module_sandbox_matrix.py"
BACKEND_PYTHON = REPO_ROOT / "backend" / ".venv" / "bin" / "python"


def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(BACKEND_PYTHON), str(MATRIX_SCRIPT), *args],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_scan_json_output() -> None:
    """--json should produce valid JSON array of module entries."""
    r = _run(["--json"])
    assert r.returncode == 0, f"exit={r.returncode}, stderr={r.stderr[:500]}"
    data = json.loads(r.stdout)
    assert isinstance(data, list)
    assert len(data) > 0, "should have at least one module entry"
    required_keys = {"module", "has_sandbox", "has_test_module", "check", "reason"}
    for entry in data:
        assert required_keys.issubset(entry.keys()), f"missing keys in {entry['module']}"
    # All entries have a check status
    checks = {e["check"] for e in data}
    assert checks.issubset({"pass", "skip", "fail"}), f"unexpected check values: {checks}"


def test_markdown_output() -> None:
    """Default output should be markdown with a table."""
    r = _run([])
    assert r.returncode == 0, f"exit={r.returncode}"
    assert "# Module Sandbox Verification Matrix" in r.stdout
    assert "| Module | Sandbox |" in r.stdout
    assert "**Summary**" in r.stdout


def test_scan_includes_known_modules() -> None:
    """Should find modules with sandboxes like agent, excel-engine, etc."""
    r = _run(["--json"])
    data = json.loads(r.stdout)
    keys = [e["module"] for e in data]
    # At least a few known modules should be present
    found = {k for k in keys if k in {"agent", "excel-engine", "image-vision", "desktop-tools"}}
    assert len(found) >= 3, f"expected 3+ known modules, got {found}"


def test_agent_has_sandbox() -> None:
    """agent module should have a sandbox and backend."""
    r = _run(["--json"])
    data = json.loads(r.stdout)
    agent = next((e for e in data if e["module"] == "agent"), None)
    assert agent is not None, "agent entry not found"
    assert agent["has_sandbox"] is True
    assert agent["has_backend"] is True


def test_excel_engine_has_test_module() -> None:
    """excel-engine should have test_module.py in sandbox."""
    r = _run(["--json"])
    data = json.loads(r.stdout)
    ee = next((e for e in data if e["module"] == "excel-engine"), None)
    assert ee is not None
    assert ee["has_test_module"] is True, "excel-engine should have test_module.py"


def test_edge_cases() -> None:
    """Edge cases: no args should not crash, --help should work."""
    r = subprocess.run(
        [str(BACKEND_PYTHON), str(MATRIX_SCRIPT), "--help"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert r.returncode == 0
    assert "usage:" in r.stdout.lower()


if __name__ == "__main__":
    test_scan_json_output()
    test_markdown_output()
    test_scan_includes_known_modules()
    test_agent_has_sandbox()
    test_excel_engine_has_test_module()
    test_edge_cases()
    print("\nAll sandbox matrix tests PASS")
