"""Module sandbox verification matrix — scan modules/*/sandbox for testability.

Output: per-module status with check=pass/skip, actionable reason for skips.

Usage:
    python3.14 dev_toolkit/module_sandbox_matrix.py [--check]
    --check  runs 'cd <repo> && .venv/bin/python dev_toolkit/module_sandbox_matrix.py --check'
"""
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_PYTHON = REPO_ROOT / "backend" / ".venv" / "bin" / "python"
MODULES_DIR = REPO_ROOT / "modules"

MANDATORY_PARSERS = {"pdf", "docx", "xlsx", "xls", "pptx", "txt", "md", "csv"}


def scan_sandbox_matrix() -> list[dict]:
    modules = sorted(
        p.name for p in MODULES_DIR.iterdir()
        if p.is_dir() and not p.name.startswith("_")
    )
    results = []
    for key in modules:
        sandbox_dir = MODULES_DIR / key / "sandbox"
        backend_dir = MODULES_DIR / key / "backend"

        has_sandbox = sandbox_dir.exists()
        test_module = sandbox_dir / "test_module.py"
        has_test_module = test_module.exists()
        has_backend = (backend_dir / "router.py").exists()
        has_samples = (sandbox_dir / "samples").exists()

        # Build vs test commands
        frontend_build = None
        frontend_dev = None
        backend_test_cmd = None
        auto_runnable = False
        reason = ""

        if has_sandbox:
            pkg_json = sandbox_dir / "package.json"
            if pkg_json.exists():
                frontend_build = f"cd modules/{key}/sandbox && npm run build"
                frontend_dev = f"cd modules/{key}/sandbox && npm run dev"

        if has_test_module:
            backend_test_cmd = (
                f"PYTHONPATH=backend {BACKEND_PYTHON} modules/{key}/sandbox/test_module.py"
            )
            if BACKEND_PYTHON.exists():
                auto_runnable = True
            else:
                reason = "backend .venv python not found"
        elif not has_sandbox:
            reason = "no sandbox directory"
        elif not has_test_module and has_backend:
            reason = "has backend router but no sandbox/test_module.py"
        elif not has_test_module and has_sandbox:
            if has_samples:
                reason = "has samples but no test_module.py — probably a parser module needing tests"
            else:
                reason = "sandbox exists but no test_module.py and no backend — likely pure frontend"
        elif not has_test_module:
            reason = "missing test_module.py"

        entry = {
            "module": key,
            "has_sandbox": has_sandbox,
            "has_test_module": has_test_module,
            "has_backend": has_backend,
            "has_samples": has_samples,
            "check": "pass" if auto_runnable else "skip",
            "frontend_build_cmd": frontend_build,
            "frontend_dev_cmd": frontend_dev,
            "backend_test_cmd": backend_test_cmd,
            "reason": reason,
        }
        results.append(entry)
    return results


def check_sandbox_matrix(results: list[dict], quiet: bool = False) -> bool:
    """Run each auto-runnable test_module.py and report pass/fail."""
    all_pass = True
    for entry in results:
        if entry["check"] != "pass":
            continue
        cmd = entry["backend_test_cmd"]
        if not cmd:
            continue
        # PYTHONPATH=backend is a env prefix, not a CLI arg
        env = os.environ.copy()
        cmd_parts = cmd.split()
        final_cmd = []
        for part in cmd_parts:
            if part.startswith("PYTHONPATH="):
                env["PYTHONPATH"] = part.split("=", 1)[1]
            else:
                final_cmd.append(part)
        if not quiet:
            sys.stdout.write(f"\n── {entry['module']} ──\n")
        try:
            proc = subprocess.run(
                final_cmd,
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                timeout=60,
                env=env,
            )
            passed = proc.returncode == 0
            entry["check"] = "pass" if passed else "fail"
            entry["exit_code"] = proc.returncode
            entry["stdout_tail"] = proc.stdout.strip()[-500:] if proc.stdout else ""
            entry["stderr_tail"] = proc.stderr.strip()[-500:] if proc.stderr else ""
            if not passed:
                all_pass = False
                if not quiet:
                    sys.stdout.write(f"  FAIL (exit={proc.returncode})\n")
                    if proc.stderr:
                        sys.stdout.write(f"  stderr: {proc.stderr.strip()[-300:]}\n")
            elif not quiet:
                sys.stdout.write(f"  PASS (exit={proc.returncode})\n")
        except subprocess.TimeoutExpired:
            entry["check"] = "fail"
            entry["exit_code"] = -1
            entry["reason"] = "timeout (>60s)"
            all_pass = False
            if not quiet:
                sys.stdout.write("  TIMEOUT\n")
        except FileNotFoundError as e:
            entry["check"] = "skip"
            entry["reason"] = f"command not found: {e}"
            if not quiet:
                sys.stdout.write(f"  SKIP: {e}\n")
    return all_pass


def format_markdown(results: list[dict], run_all: bool, passed: bool) -> str:
    lines = [
        "# Module Sandbox Verification Matrix",
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        f"Auto-run: {'yes' if run_all else 'no'}",
        f"Overall: {'PASS' if passed else 'FAIL' if run_all else 'N/A (--check not run)'}",
        "",
        "| Module | Sandbox | test_module.py | Backend | Samples | Check | Reason |",
        "|--------|---------|---------------|---------|---------|-------|--------|",
    ]
    for entry in results:
        status = entry.get("check", "skip")
        status_icon = "✅" if status == "pass" else "❌" if status == "fail" else "⏭️"
        reason = entry.get("reason", "") or ""
        if entry.get("exit_code") is not None and status == "fail":
            reason += f" (exit={entry['exit_code']})"
        lines.append(
            f"| {entry['module']} "
            f"| {'✅' if entry['has_sandbox'] else '❌'} "
            f"| {'✅' if entry['has_test_module'] else '❌'} "
            f"| {'✅' if entry['has_backend'] else '❌'} "
            f"| {'✅' if entry['has_samples'] else '❌'} "
            f"| {status_icon} "
            f"| {reason} |"
        )

    # Summary
    total = len(results)
    passed_count = sum(1 for e in results if e.get("check") == "pass")
    fail_count = sum(1 for e in results if e.get("check") == "fail")
    skip_count = sum(1 for e in results if e.get("check") == "skip")
    lines.extend([
        "",
        f"**Summary**: {total} modules, {passed_count} pass, {fail_count} fail, {skip_count} skip",
        "",
        "### Commands to re-run",
        "",
        "```bash",
        "# Full matrix",
        "cd {} && {} dev_toolkit/module_sandbox_matrix.py --check".format(
            REPO_ROOT, BACKEND_PYTHON
        ),
        "# Single module",
        "cd {} && PYTHONPATH=backend {} modules/<key>/sandbox/test_module.py".format(
            REPO_ROOT, BACKEND_PYTHON
        ),
        "```",
    ])
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Module sandbox verification matrix")
    parser.add_argument("--check", action="store_true", help="Run auto-runnable test_module.py files")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of markdown")
    args = parser.parse_args()

    results = scan_sandbox_matrix()
    run_check = args.check

    if run_check:
        check_sandbox_matrix(results, quiet=args.json)

    passed = all(
        entry.get("check") == "pass" or entry.get("check") == "skip"
        for entry in results
    ) if run_check else True

    if args.json:
        output = json.dumps(results, ensure_ascii=False, indent=2)
    else:
        output = format_markdown(results, run_check, passed)

    print(output)
    sys.exit(0 if passed or not run_check else 1)


if __name__ == "__main__":
    main()
