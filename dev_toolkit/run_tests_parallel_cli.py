"""CLI entry for tool_job_submit(run_tests_parallel)."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dev_toolkit.code_tools import run_tests_parallel  # noqa: E402
from dev_toolkit.process_tools import create_subprocess_exec_group, terminate_process_tree  # noqa: E402


async def _run_command_json(cmd, *, cwd: Path, timeout: int = 120, env: dict | None = None):
    started = time.monotonic()
    proc = await create_subprocess_exec_group(
        *cmd,
        cwd=str(cwd),
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    timed_out = False
    try:
        stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        timed_out = True
        await terminate_process_tree(proc)
        stdout_b, stderr_b = b"", b"timeout"
    stdout = (stdout_b or b"").decode("utf-8", errors="replace")
    stderr = (stderr_b or b"").decode("utf-8", errors="replace")
    returncode = proc.returncode if proc.returncode is not None else -1
    return {
        "success": (returncode == 0) and not timed_out,
        "returncode": returncode,
        "stdout": stdout,
        "stderr": stderr,
        "stdout_tail": stdout[-8000:],
        "stderr_tail": stderr[-4000:],
        "duration_seconds": round(time.monotonic() - started, 3),
        "timeout": timed_out,
        "timeout_seconds": timeout,
        "cwd": str(cwd),
        "command": cmd,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Parallel pytest fan-out for project toolkit")
    parser.add_argument("--targets", required=True, help="targets string or JSON list")
    parser.add_argument("--max-workers", type=int, default=4)
    parser.add_argument("--timeout-per-target", type=int, default=120)
    parser.add_argument("--mode", default="auto", choices=["auto", "force_parallel", "serial"])
    args = parser.parse_args()

    raw = asyncio.run(
        run_tests_parallel(
            _run_command_json,
            REPO_ROOT,
            targets=args.targets,
            max_workers=args.max_workers,
            timeout_per_target=args.timeout_per_target,
            mode=args.mode,
        )
    )
    print(raw)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return 1
    return 0 if data.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
