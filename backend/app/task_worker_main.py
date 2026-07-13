"""Standalone background task Dispatcher process."""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import signal

from sqlalchemy import text as sa_text

from app.database import AsyncSessionLocal, dispose_db, engine, init_db
from app.models.system import ensure_framework_scheduling_columns
from app.services.module_logger import setup_module_logging, setup_v2_loggers_for_modules
from app.services.task_dispatcher import (
    dispatcher_health,
    execute_claimed_task,
    start_dispatcher,
    stop_dispatcher,
)
from app.services.task_handler_bootstrap import bootstrap_task_handlers

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("v2.task_worker_main")
RETIRE_SHUTDOWN_TIMEOUT_SECONDS = float(os.getenv("TASK_WORKER_RETIRE_SHUTDOWN_TIMEOUT_SECONDS", "15"))

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Huashi task Dispatcher")
    parser.add_argument("--executor-task-id", type=int, default=0)
    parser.add_argument("--lease-token", default="")
    return parser.parse_args()
async def _startup(*, start_dispatcher_process: bool) -> None:
    await init_db()
    await ensure_framework_scheduling_columns()
    try:
        async with engine.begin() as conn:
            await conn.execute(sa_text("SET LOCAL lock_timeout = '1000ms'"))
            await conn.execute(sa_text("SET LOCAL statement_timeout = '10000ms'"))
            origin_type_exists = await conn.scalar(
                sa_text(
                    """
                    SELECT EXISTS (
                        SELECT 1
                        FROM information_schema.columns
                        WHERE table_schema = current_schema()
                          AND table_name = 'framework_content_packages'
                          AND column_name = 'origin_type'
                    )
                    """
                )
            )
            if not origin_type_exists:
                await conn.execute(sa_text(
                    "ALTER TABLE framework_content_packages "
                    "ADD COLUMN origin_type VARCHAR(32) DEFAULT 'uploaded'"
                ))
    except Exception as exc:
        logger.warning("Migration origin_type skipped: %s", exc)

    setup_module_logging()
    bootstrap_task_handlers()
    setup_v2_loggers_for_modules()

    # Touch the DB after module import so startup fails early if credentials drift.
    async with AsyncSessionLocal() as db:
        await db.execute(sa_text("SELECT 1"))

    if start_dispatcher_process:
        start_dispatcher()
        logger.info("Standalone task dispatcher started: %s", dispatcher_health())


async def _run_forever() -> None:
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:
            pass

    await _startup(start_dispatcher_process=True)
    stop_task = asyncio.create_task(stop_event.wait())
    try:
        await stop_task
    finally:
        stop_task.cancel()
        await asyncio.gather(stop_task, return_exceptions=True)
        logger.info("Standalone task dispatcher stopping")
        try:
            await asyncio.wait_for(
                stop_dispatcher(),
                timeout=max(1.0, RETIRE_SHUTDOWN_TIMEOUT_SECONDS),
            )
            await dispose_db()
        except asyncio.TimeoutError:
            logger.error(
                "Standalone task worker shutdown exceeded %.1fs",
                RETIRE_SHUTDOWN_TIMEOUT_SECONDS,
            )
            raise


async def _run_executor_once(task_id: int, lease_token: str) -> int:
    await _startup(start_dispatcher_process=False)
    try:
        return await execute_claimed_task(task_id, lease_token)
    finally:
        await dispose_db()


def main() -> None:
    args = _parse_args()
    if args.executor_task_id:
        if not args.lease_token:
            raise SystemExit("--lease-token is required with --executor-task-id")
        raise SystemExit(asyncio.run(_run_executor_once(args.executor_task_id, args.lease_token)))
    asyncio.run(_run_forever())


if __name__ == "__main__":
    main()
