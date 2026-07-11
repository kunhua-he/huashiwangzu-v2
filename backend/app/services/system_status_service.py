import os
import socket

import psutil
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.model_watchdog.watchdog import status_all


def _is_port_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(3)
        return sock.connect_ex((host, port)) == 0


async def check_backend() -> dict:
    return {"status": True, "message": "Running normally"}


async def check_database(db: AsyncSession) -> dict:
    try:
        await db.execute(text("SELECT 1"))
        return {"status": True, "message": "Connection OK"}
    except Exception as e:
        return {"status": False, "message": f"DB connection failed: {type(e).__name__}"}


async def check_worker() -> dict:
    """Check for background task worker using task_worker module.

    Uses the same worker_health() as /api/health, not process name scanning.
    """
    from app.services.task_worker import worker_health
    wh = worker_health()
    running = wh.get("running", False)
    external = os.getenv("TASK_WORKER_AUTOSTART", "1").strip().lower() in {"0", "false", "no", "off"}
    healthy = running or external
    if running:
        message = "Background worker is running"
    elif external:
        message = "Background worker uses external watchdog supervision"
    else:
        message = "Background worker is not running"
    return {
        "status": healthy,
        "message": message,
    }


async def check_model_service() -> dict:
    try:
        statuses = status_all()
        healthy = [name for name, ok in statuses.items() if ok]
        if healthy:
            return {
                "status": True,
                "message": f"Model gateway reachable: {', '.join(healthy)}",
            }
        return {"status": False, "message": "No registered model endpoint reachable"}
    except Exception as e:
        return {"status": False, "message": f"Model service check error: {type(e).__name__}"}


async def check_entry() -> dict:
    host = "127.0.0.1"
    port = 80
    try:
        if _is_port_open(host, port):
            return {"status": True, "message": f"Port {port} is listening"}
        return {"status": False, "message": f"Port {port} not listening"}
    except Exception as e:
        return {"status": False, "message": f"Entry check error: {str(e)}"}


async def get_system_status(db: AsyncSession) -> dict:
    backend = await check_backend()
    database = await check_database(db)
    worker = await check_worker()
    model = await check_model_service()
    entry = await check_entry()
    cpu = psutil.cpu_percent(interval=0.1)
    mem = psutil.virtual_memory().percent
    return {
        "backend": backend, "database": database,
        "worker": worker, "model_service": model, "entry": entry,
        "cpu_percent": cpu, "memory_percent": mem,
    }
