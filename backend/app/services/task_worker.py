"""Framework-level background task worker.

Consumes SystemTaskQueue (framework_system_task_queues). Concurrency-safe via
FOR UPDATE SKIP LOCKED. Modules register handlers by task_type.
"""
import asyncio
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Awaitable, Callable

from sqlalchemy import and_, or_, select, text, update

from app.database import AsyncSessionLocal, engine
from app.models.system import SystemTaskQueue
from app.services.module_registry import semantic_failure_reason

logger = logging.getLogger("v2.task_worker")

POLL_INTERVAL_SECONDS = 2.0
RUNNING_TIMEOUT_SECONDS = 1200  # running 超过 20 分钟视为死任务，回收重排
CONFIG_RELOAD_SECONDS = 5.0
DEFAULT_MAX_LANES_PER_PROCESS = 16
ABSOLUTE_MAX_LANES_PER_PROCESS = 128
CONFIG_PATH = Path(__file__).resolve().parents[2] / "data" / "config" / "task_worker.json"
WORKER_LEADER_LOCK_KEY = 94022025


@dataclass(frozen=True)
class WorkerConfig:
    worker_lanes_per_process: int = 1
    max_lanes_per_process: int = DEFAULT_MAX_LANES_PER_PROCESS
    poll_interval_seconds: float = POLL_INTERVAL_SECONDS
    running_timeout_seconds: int = RUNNING_TIMEOUT_SECONDS
    config_reload_seconds: float = CONFIG_RELOAD_SECONDS
    reclaim_running_on_startup: bool = False
    startup_reclaim_min_age_seconds: int = 10

# task_type -> async handler(parameters: dict) -> dict | None
TaskHandler = Callable[[dict], Awaitable[dict | None]]
_HANDLERS: dict[str, TaskHandler] = {}

_worker_task: asyncio.Task | None = None
_lane_tasks: dict[int, asyncio.Task] = {}
_lane_current_task_ids: dict[int, int] = {}
_retiring_lane_ids: set[int] = set()
_next_lane_id = 1
_stop_flag = False
_last_active: datetime | None = None
_runtime_config = WorkerConfig()
_config_mtime: float | None = None
_worker_is_leader = False


def register_task_handler(task_type: str, handler: TaskHandler) -> None:
    """模块调用此函数注册自己的任务处理器。"""
    _HANDLERS[task_type] = handler
    logger.info("Registered task handler: %s", task_type)


def has_task_handler(task_type: str) -> bool:
    return task_type in _HANDLERS


async def _echo_handler(parameters: dict) -> dict:
    """内置自检处理器，用于验证 worker 链路。"""
    return {"echo": parameters}


_HANDLERS["_echo"] = _echo_handler


def _clamp_int(value: object, default: int, min_value: int, max_value: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(min_value, min(max_value, parsed))


def _clamp_float(value: object, default: float, min_value: float, max_value: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return max(min_value, min(max_value, parsed))


def _coerce_bool(value: object, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    if value is None:
        return default
    return bool(value)


def _parse_worker_config(raw: dict | None) -> WorkerConfig:
    raw = raw or {}
    max_lanes_per_process = _clamp_int(
        raw.get("max_lanes_per_process"),
        WorkerConfig.max_lanes_per_process,
        1,
        ABSOLUTE_MAX_LANES_PER_PROCESS,
    )
    return WorkerConfig(
        worker_lanes_per_process=_clamp_int(
            raw.get("worker_lanes_per_process"),
            WorkerConfig.worker_lanes_per_process,
            0,
            max_lanes_per_process,
        ),
        max_lanes_per_process=max_lanes_per_process,
        poll_interval_seconds=_clamp_float(
            raw.get("poll_interval_seconds"),
            WorkerConfig.poll_interval_seconds,
            0.2,
            60.0,
        ),
        running_timeout_seconds=_clamp_int(
            raw.get("running_timeout_seconds"),
            WorkerConfig.running_timeout_seconds,
            60,
            24 * 60 * 60,
        ),
        config_reload_seconds=_clamp_float(
            raw.get("config_reload_seconds"),
            WorkerConfig.config_reload_seconds,
            1.0,
            300.0,
        ),
        reclaim_running_on_startup=_coerce_bool(
            raw.get("reclaim_running_on_startup"),
            WorkerConfig.reclaim_running_on_startup,
        ),
        startup_reclaim_min_age_seconds=_clamp_int(
            raw.get("startup_reclaim_min_age_seconds"),
            WorkerConfig.startup_reclaim_min_age_seconds,
            0,
            3600,
        ),
    )


def _load_worker_config(force: bool = False) -> WorkerConfig:
    global _config_mtime, _runtime_config
    try:
        stat = CONFIG_PATH.stat()
    except FileNotFoundError:
        if force:
            _runtime_config = WorkerConfig()
        return _runtime_config
    except OSError as exc:
        logger.warning("Task worker config stat failed: %s", exc)
        return _runtime_config

    if not force and _config_mtime == stat.st_mtime:
        return _runtime_config

    try:
        raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("config root must be an object")
    except Exception as exc:
        logger.warning("Task worker config load failed: %s", exc)
        return _runtime_config

    next_config = _parse_worker_config(raw)
    if next_config != _runtime_config:
        logger.info("Task worker config loaded: %s", next_config)
    _runtime_config = next_config
    _config_mtime = stat.st_mtime
    return _runtime_config


async def _reconcile_one_orphan(task: SystemTaskQueue, now: datetime) -> None:
    """Increment retry_count on an orphan task and fail it if over limit."""
    task.retry_count = (task.retry_count or 0) + 1
    if task.retry_count >= (task.max_retries or 3):
        task.status = "failed"
        task.error_message = "Orphan task exceeded max retries on startup recovery"
        task.completed_at = now
    else:
        task.status = "pending"
        task.started_at = None


async def _recover_stale_tasks(db, running_timeout_seconds: int | None = None) -> None:
    now = datetime.now(timezone.utc)
    timeout = running_timeout_seconds or _runtime_config.running_timeout_seconds
    cutoff = now - timedelta(seconds=timeout)

    # Phase 1: timeout-reclaim — running tasks older than cutoff
    result = await db.execute(
        select(SystemTaskQueue)
        .where(SystemTaskQueue.status == "running", SystemTaskQueue.started_at < cutoff)
        .with_for_update(skip_locked=True)
    )
    stale = list(result.scalars().all())
    reclaimed_count = 0
    for task in stale:
        retry_count = (task.retry_count or 0) + 1
        if retry_count >= (task.max_retries or 3):
            values = {
                "retry_count": retry_count,
                "status": "failed",
                "error_message": "Task timed out and exceeded max retries",
                "completed_at": now,
            }
        else:
            values = {
                "retry_count": retry_count,
                "status": "pending",
                "started_at": None,
            }
        update_result = await db.execute(
            update(SystemTaskQueue)
            .where(
                SystemTaskQueue.id == task.id,
                SystemTaskQueue.status == "running",
                SystemTaskQueue.started_at == task.started_at,
            )
            .values(**values)
        )
        reclaimed_count += int(update_result.rowcount or 0)
    if reclaimed_count:
        logger.info("Timeout recovery: reclaimed %d stale tasks", reclaimed_count)
    await db.commit()


async def _recover_orphan_running_tasks() -> None:
    """Startup recovery: reclaim only timed-out running tasks.

    In multi-worker deployments another worker may legitimately be executing a
    fresh ``running`` task while this worker starts. Treating every running task
    as orphaned causes duplicate retries, so startup recovery uses the same
    timeout + row-lock path as periodic stale recovery.
    """
    try:
        async with AsyncSessionLocal() as db:
            await _recover_stale_tasks(db, _runtime_config.running_timeout_seconds)
    except Exception as exc:
        logger.error("Orphan recovery failed: %s", exc)


async def _acquire_worker_leader_connection():
    conn = await engine.connect()
    try:
        result = await conn.execute(
            text("select pg_try_advisory_lock(:lock_key)"),
            {"lock_key": WORKER_LEADER_LOCK_KEY},
        )
        acquired = bool(result.scalar())
        await conn.commit()
        if acquired:
            return conn
        await conn.close()
        return None
    except Exception as exc:
        logger.warning("Task worker leader lock acquire failed: %s", exc)
        await conn.close()
        return None


async def _release_worker_leader_connection(conn) -> None:
    try:
        await conn.execute(
            text("select pg_advisory_unlock(:lock_key)"),
            {"lock_key": WORKER_LEADER_LOCK_KEY},
        )
        await conn.commit()
    except Exception as exc:
        logger.warning("Task worker leader lock release failed: %s", exc)
    finally:
        await conn.close()


async def _reclaim_running_tasks_on_startup(min_age_seconds: int = 10) -> None:
    """Release DB-running tasks when this deployment restarts as a single owner.

    This is intentionally config-gated. The default timeout recovery is safer
    for multi-instance deployments; local enterprise imports prefer immediate
    restart recovery because the queue is DB-persisted and the watchdog restarts
    the only backend owner.
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(seconds=max(0, int(min_age_seconds or 0)))
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                update(SystemTaskQueue)
                .where(
                    SystemTaskQueue.status == "running",
                    SystemTaskQueue.started_at < cutoff,
                )
                .values(
                    status="pending",
                    started_at=None,
                    error_message="Task reclaimed on worker startup; released for retry",
                    updated_at=now,
                )
            )
            await db.commit()
            reclaimed = int(result.rowcount or 0)
            if reclaimed:
                logger.info(
                    "Startup recovery: reclaimed %d running task(s) older than %ss",
                    reclaimed,
                    min_age_seconds,
                )
    except Exception as exc:
        logger.error("Startup running-task reclaim failed: %s", exc)


def _result_is_semantic_failure(result: dict | None) -> tuple[bool, str | None]:
    """Return whether a handler result is a business failure contract."""
    reason = semantic_failure_reason(result)
    return reason is not None, reason


async def _claim_one_task(db) -> SystemTaskQueue | None:
    """原子抢占一条 pending 任务（FOR UPDATE SKIP LOCKED 防多 worker 抢同一条）。

    即时任务(scheduled_at IS NULL)照旧立即执行；
    定时任务(scheduled_at <= now())到点才被取。
    """
    now = datetime.now(timezone.utc)
    row = await db.execute(
        select(SystemTaskQueue)
        .where(
            and_(
                SystemTaskQueue.status == "pending",
                or_(
                    SystemTaskQueue.scheduled_at.is_(None),
                    SystemTaskQueue.scheduled_at <= now,
                ),
            )
        )
        .order_by(SystemTaskQueue.priority.desc(), SystemTaskQueue.id)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    task = row.scalar_one_or_none()
    if not task:
        return None
    task.status = "running"
    task.started_at = datetime.now(timezone.utc)
    task.completed_at = None
    task.error_message = None
    task.result = None
    await db.commit()
    await db.refresh(task)
    return task


async def _run_handler(task: SystemTaskQueue) -> tuple[bool, dict | None, str | None]:
    handler = _HANDLERS.get(task.task_type)
    if not handler:
        return False, None, f"No handler registered for task_type '{task.task_type}'"
    try:
        params = json.loads(task.parameters) if task.parameters else {}
    except Exception as exc:
        return False, None, f"Invalid parameters JSON: {exc}"
    try:
        result = await handler(params)
        failed, error = _result_is_semantic_failure(result)
        if failed:
            return False, result, error
        return True, result, None
    except Exception as exc:
        logger.error("Task %s (%s) handler failed: %s", task.id, task.task_type, exc)
        return False, None, str(exc)


def _compute_next_recur(recur: str, ref_time: datetime) -> datetime | None:
    """根据周期表达计算下一次运行时间。"""
    ref = ref_time.astimezone(timezone.utc)
    if recur == "hourly":
        return ref + timedelta(hours=1)
    elif recur == "daily":
        return ref + timedelta(days=1)
    elif recur == "weekly":
        return ref + timedelta(weeks=1)
    elif recur.startswith("cron:"):
        # Minimal cron: "cron:HH:MM" daily at that UTC time
        parts = recur.split(":")
        if len(parts) >= 3:
            hour, minute = int(parts[1]), int(parts[2])
            next_time = ref.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if next_time <= ref:
                next_time += timedelta(days=1)
            return next_time
    return None


def _serialize_task_result(result: dict | None) -> str | None:
    return json.dumps(result, ensure_ascii=False, default=str) if result is not None else None


async def _finish_task(db, task_id: int, ok: bool, result: dict | None, error: str | None) -> None:
    task = await db.get(SystemTaskQueue, task_id)
    if not task:
        return
    now = datetime.now(timezone.utc)
    if ok:
        task.status = "completed"
        task.result = _serialize_task_result(result)
        task.error_message = None
        task.completed_at = now
        # 周期任务: 完成后自动重排下一次
        if task.recur:
            next_time = _compute_next_recur(task.recur, now)
            if next_time:
                task.status = "pending"
                task.scheduled_at = next_time
                task.next_run_at = next_time
                task.started_at = None
                task.retry_count = 0
                task.completed_at = None
    else:
        task.retry_count = (task.retry_count or 0) + 1
        task.error_message = error
        if task.retry_count >= (task.max_retries or 3):
            task.status = "failed"
            task.completed_at = now
        else:
            task.status = "pending"  # 重排重试
            task.started_at = None
    await db.commit()


def _active_task_ids_snapshot() -> list[int]:
    return sorted(set(_lane_current_task_ids.values()))


async def _release_active_tasks_on_shutdown(task_ids: list[int] | None = None) -> None:
    """Return tasks owned by this process to the DB queue during graceful restart.

    Startup recovery only reclaims timed-out tasks because multiple uvicorn
    workers may be alive at once. During process shutdown, however, this process
    knows exactly which task IDs its lanes claimed, so releasing only those tasks
    avoids both duplicate execution and 20-minute stale waits after a restart.
    """
    task_ids = sorted(set(task_ids or _active_task_ids_snapshot()))
    if not task_ids:
        return

    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                update(SystemTaskQueue)
                .where(
                    SystemTaskQueue.id.in_(task_ids),
                    SystemTaskQueue.status == "running",
                )
                .values(
                    status="pending",
                    started_at=None,
                    error_message="Task interrupted by worker shutdown; released for retry",
                )
            )
            await db.commit()
            released = int(result.rowcount or 0)
            if released:
                logger.info("Released %d running task(s) during worker shutdown", released)
    except Exception as exc:
        logger.error("Failed to release running tasks during worker shutdown: %s", exc)


async def _worker_lane_loop(lane_id: int) -> None:
    global _last_active
    logger.info("Task worker lane %s started", lane_id)
    while not _stop_flag and lane_id not in _retiring_lane_ids:
        config = _runtime_config
        try:
            async with AsyncSessionLocal() as db:
                await _recover_stale_tasks(db, config.running_timeout_seconds)
                task = await _claim_one_task(db)
            if task is None:
                await asyncio.sleep(config.poll_interval_seconds)
                continue
            _last_active = datetime.now(timezone.utc)
            _lane_current_task_ids[lane_id] = int(task.id)
            try:
                ok, result, error = await _run_handler(task)
                async with AsyncSessionLocal() as db:
                    await _finish_task(db, task.id, ok, result, error)
            finally:
                _lane_current_task_ids.pop(lane_id, None)
        except Exception as exc:
            logger.error("Task worker lane %s error: %s", lane_id, exc)
            await asyncio.sleep(config.poll_interval_seconds)
    logger.info("Task worker lane %s stopped", lane_id)


def _start_lane() -> None:
    global _next_lane_id
    lane_id = _next_lane_id
    _next_lane_id += 1
    _lane_tasks[lane_id] = asyncio.create_task(_worker_lane_loop(lane_id))


def _reconcile_lanes(target_count: int) -> None:
    for lane_id, task in list(_lane_tasks.items()):
        if task.done():
            _lane_tasks.pop(lane_id, None)
            _retiring_lane_ids.discard(lane_id)

    active_count = len(_lane_tasks)
    if active_count <= target_count:
        _retiring_lane_ids.clear()

    while active_count < target_count:
        _start_lane()
        active_count += 1

    if active_count > target_count:
        active_lane_ids = sorted(_lane_tasks.keys(), reverse=True)
        for lane_id in active_lane_ids[: active_count - target_count]:
            _retiring_lane_ids.add(lane_id)


async def _worker_supervisor_loop() -> None:
    global _worker_is_leader
    logger.info("Task worker supervisor started")
    _load_worker_config(force=True)
    while not _stop_flag:
        config = _load_worker_config()
        leader_conn = None
        try:
            leader_conn = await _acquire_worker_leader_connection()
            if leader_conn is None:
                _worker_is_leader = False
                _reconcile_lanes(0)
                await asyncio.sleep(config.config_reload_seconds)
                continue

            _worker_is_leader = True
            logger.info("Task worker leader lock acquired by pid=%s", os.getpid())
            if config.reclaim_running_on_startup:
                await _reclaim_running_tasks_on_startup(config.startup_reclaim_min_age_seconds)
            else:
                await _recover_orphan_running_tasks()

            while not _stop_flag:
                config = _load_worker_config()
                _reconcile_lanes(config.worker_lanes_per_process)
                await asyncio.sleep(config.config_reload_seconds)
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.error("Task worker supervisor error: %s", exc)
            _worker_is_leader = False
            _reconcile_lanes(0)
            await asyncio.sleep(config.config_reload_seconds)
        finally:
            _reconcile_lanes(0)
            if _lane_tasks:
                await asyncio.gather(*_lane_tasks.values(), return_exceptions=True)
            if leader_conn is not None:
                await _release_worker_leader_connection(leader_conn)

    _worker_is_leader = False
    _reconcile_lanes(0)
    if _lane_tasks:
        await asyncio.gather(*_lane_tasks.values(), return_exceptions=True)
    logger.info("Task worker supervisor stopped")


def start_worker() -> None:
    global _worker_task, _stop_flag
    if _worker_task is not None and not _worker_task.done():
        return
    _stop_flag = False
    _worker_task = asyncio.create_task(_worker_supervisor_loop())


async def stop_worker() -> None:
    global _stop_flag
    _stop_flag = True
    if _worker_task:
        active_task_ids = _active_task_ids_snapshot()
        try:
            timeout = _runtime_config.poll_interval_seconds + _runtime_config.config_reload_seconds + 1
            await asyncio.wait_for(_worker_task, timeout=timeout)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            _worker_task.cancel()
            for lane_task in _lane_tasks.values():
                lane_task.cancel()
            if _lane_tasks:
                await asyncio.gather(*_lane_tasks.values(), return_exceptions=True)
        finally:
            await _release_active_tasks_on_shutdown(active_task_ids)


def worker_health() -> dict:
    return {
        "running": _worker_task is not None and not _worker_task.done(),
        "configured_lanes_per_process": _runtime_config.worker_lanes_per_process,
        "max_lanes_per_process": _runtime_config.max_lanes_per_process,
        "active_lanes": len([task for task in _lane_tasks.values() if not task.done()]),
        "active_task_ids": _active_task_ids_snapshot(),
        "retiring_lanes": sorted(_retiring_lane_ids),
        "config_path": str(CONFIG_PATH),
        "config_reload_seconds": _runtime_config.config_reload_seconds,
        "reclaim_running_on_startup": _runtime_config.reclaim_running_on_startup,
        "startup_reclaim_min_age_seconds": _runtime_config.startup_reclaim_min_age_seconds,
        "is_leader": _worker_is_leader,
        "leader_lock_key": WORKER_LEADER_LOCK_KEY,
        "registered_handlers": sorted(_HANDLERS.keys()),
        "last_active": _last_active.isoformat() if _last_active else None,
        "process_local": True,
        "pid": os.getpid(),
        "last_active_scope": "process",
    }
