#!/usr/bin/env python3
"""CLI used by backend_watchdog.sh to decide when a safe restart may proceed."""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
for path in (PROJECT_ROOT, BACKEND_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from app.database import AsyncSessionLocal
from app.services.maintenance_service import (
    mark_restarting_if_ready,
    restart_preflight,
    restart_signal_path,
)


async def _main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--preflight-only",
        action="store_true",
        help="check blockers without requiring or changing the maintenance restart signal",
    )
    args = parser.parse_args()
    if args.preflight_only:
        async with AsyncSessionLocal() as db:
            result = await restart_preflight(db)
        print(json.dumps(result, ensure_ascii=False, default=str))
        return 0 if result.get("ready") else 1

    if not restart_signal_path().exists():
        print(json.dumps({"ready": False, "reason": "no_restart_signal"}))
        return 1
    async with AsyncSessionLocal() as db:
        result = await mark_restarting_if_ready(db)
    print(json.dumps(result, ensure_ascii=False, default=str))
    return 0 if result.get("ready") else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
