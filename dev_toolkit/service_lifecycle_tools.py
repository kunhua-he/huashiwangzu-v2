"""Website/service lifecycle tools for the project toolkit MCP.

Covers Postgres + PgBouncer + backend (with watchdog) + frontend so agents can
bring the stack up after a reboot without hunting shell scripts.
"""

from __future__ import annotations

import asyncio
import json
import os
import signal
import socket
import subprocess
import time
from pathlib import Path
from typing import Any
from urllib import error as urlerror
from urllib import request as urlrequest

TOOL_NAMES = {
    "service_status",
    "start_backend",
    "stop_backend",
    "start_frontend",
    "stop_frontend",
    "start_stack",
    "stop_stack",
    "restart_backend",
}

BACKEND_PORT = 33000
FRONTEND_PORT = 5173
POSTGRES_PORT = 5432
PGBOUNCER_PORT = 6432

_FLYENV_PG_START = Path.home() / "Library/FlyEnv/server/postgresql/start-17.10.sh"
_FLYENV_PG_CTL = Path.home() / "Library/FlyEnv/env/postgresql/bin/pg_ctl"
_FLYENV_PG_DATA = Path.home() / "Library/FlyEnv/server/postgresql/postgresql17"


def tool_definitions() -> list[Any]:
    from mcp.types import Tool

    return [
        Tool(
            name="service_status",
            description=(
                "查看本机华世王镞相关服务状态：PostgreSQL(5432)、PgBouncer(6432)、"
                "后端 FastAPI(33000)、前端 Vite(5173)、watchdog 与健康检查。"
            ),
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="start_backend",
            description=(
                "启动后端（含 backend-watchdog）。默认会先确保 Postgres+PgBouncer 可用，"
                "再执行 scripts/start_backend.sh。已运行则只校验健康。"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "with_db": {
                        "type": "boolean",
                        "description": "是否先拉起 Postgres 与 PgBouncer",
                        "default": True,
                    },
                    "wait_seconds": {
                        "type": "number",
                        "description": "等待健康检查的最长时间（秒）",
                        "default": 45,
                    },
                },
            },
        ),
        Tool(
            name="stop_backend",
            description=(
                "停止后端：结束 backend-watchdog、本项目 uvicorn 与 task_worker。"
                "默认不动 Postgres/PgBouncer。"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "force": {
                        "type": "boolean",
                        "description": "SIGTERM 失败后是否 SIGKILL",
                        "default": True,
                    },
                },
            },
        ),
        Tool(
            name="start_frontend",
            description="启动前端开发服务器（cd frontend && npm run dev）。已在 5173 监听则直接返回。",
            inputSchema={
                "type": "object",
                "properties": {
                    "wait_seconds": {
                        "type": "number",
                        "description": "等待端口就绪的最长时间（秒）",
                        "default": 20,
                    },
                },
            },
        ),
        Tool(
            name="stop_frontend",
            description="停止本项目 frontend 目录下的 Vite/npm run dev 进程。",
            inputSchema={
                "type": "object",
                "properties": {
                    "force": {
                        "type": "boolean",
                        "description": "SIGTERM 失败后是否 SIGKILL",
                        "default": True,
                    },
                },
            },
        ),
        Tool(
            name="start_stack",
            description=(
                "一键启动完整开发栈：Postgres → PgBouncer → 后端 → 前端。"
                "重启电脑后优先用这个。"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "with_frontend": {
                        "type": "boolean",
                        "description": "是否启动前端",
                        "default": True,
                    },
                    "wait_seconds": {
                        "type": "number",
                        "description": "各阶段健康等待上限（秒）",
                        "default": 45,
                    },
                },
            },
        ),
        Tool(
            name="stop_stack",
            description=(
                "停止前端与后端（含 watchdog/uvicorn/task_worker）。"
                "默认保留 Postgres/PgBouncer；需要连库一起停时设 stop_db=true。"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "stop_db": {
                        "type": "boolean",
                        "description": "是否同时停止 PgBouncer 与 Postgres",
                        "default": False,
                    },
                    "force": {
                        "type": "boolean",
                        "description": "SIGTERM 失败后是否 SIGKILL",
                        "default": True,
                    },
                },
            },
        ),
        Tool(
            name="restart_backend",
            description=(
                "强制重启后端（zsh scripts/start_backend.sh --restart）。"
                "默认会先确保数据库链路可用。"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "with_db": {
                        "type": "boolean",
                        "description": "是否先拉起 Postgres 与 PgBouncer",
                        "default": True,
                    },
                    "force_restart": {
                        "type": "boolean",
                        "description": "设置 FORCE_RESTART=1，跳过任务排水门禁（紧急）",
                        "default": False,
                    },
                    "wait_seconds": {
                        "type": "number",
                        "description": "等待健康检查的最长时间（秒）",
                        "default": 45,
                    },
                },
            },
        ),
    ]


def handles_tool(name: str) -> bool:
    return name in TOOL_NAMES


async def handle_tool(repo_root: Path, name: str, arguments: dict[str, Any]) -> str:
    args = arguments or {}
    if name == "service_status":
        payload = await asyncio.to_thread(service_status, repo_root)
    elif name == "start_backend":
        payload = await asyncio.to_thread(
            start_backend,
            repo_root,
            with_db=bool(args.get("with_db", True)),
            wait_seconds=float(args.get("wait_seconds", 45) or 45),
        )
    elif name == "stop_backend":
        payload = await asyncio.to_thread(
            stop_backend,
            repo_root,
            force=bool(args.get("force", True)),
        )
    elif name == "start_frontend":
        payload = await asyncio.to_thread(
            start_frontend,
            repo_root,
            wait_seconds=float(args.get("wait_seconds", 20) or 20),
        )
    elif name == "stop_frontend":
        payload = await asyncio.to_thread(
            stop_frontend,
            repo_root,
            force=bool(args.get("force", True)),
        )
    elif name == "start_stack":
        payload = await asyncio.to_thread(
            start_stack,
            repo_root,
            with_frontend=bool(args.get("with_frontend", True)),
            wait_seconds=float(args.get("wait_seconds", 45) or 45),
        )
    elif name == "stop_stack":
        payload = await asyncio.to_thread(
            stop_stack,
            repo_root,
            stop_db=bool(args.get("stop_db", False)),
            force=bool(args.get("force", True)),
        )
    elif name == "restart_backend":
        payload = await asyncio.to_thread(
            restart_backend,
            repo_root,
            with_db=bool(args.get("with_db", True)),
            force_restart=bool(args.get("force_restart", False)),
            wait_seconds=float(args.get("wait_seconds", 45) or 45),
        )
    else:
        raise ValueError(f"未知服务生命周期工具: {name}")
    return json.dumps(payload, ensure_ascii=False, indent=2)


# ── public operations ───────────────────────────────────────────────────


def service_status(repo_root: Path) -> dict[str, Any]:
    backend_port = _backend_port(repo_root)
    pgbouncer_ini = _pgbouncer_ini(repo_root)
    status = {
        "success": True,
        "postgres": {
            "port": POSTGRES_PORT,
            "listening": _port_listening(POSTGRES_PORT),
            "accepting": _pg_isready(POSTGRES_PORT),
            "source": "flyenv" if _FLYENV_PG_CTL.exists() else "unknown",
        },
        "pgbouncer": {
            "port": PGBOUNCER_PORT,
            "listening": _port_listening(PGBOUNCER_PORT),
            "accepting": _pg_isready(PGBOUNCER_PORT),
            "config": str(pgbouncer_ini) if pgbouncer_ini.exists() else None,
            "pid": _read_pid_file(repo_root / "backend/data/config/pgbouncer/pgbouncer.pid"),
        },
        "backend": {
            "port": backend_port,
            "listening": _port_listening(backend_port),
            "health": _http_health(f"http://127.0.0.1:{backend_port}/api/health"),
            "uvicorn_pids": _project_uvicorn_pids(repo_root),
            "watchdog_pids": _watchdog_pids(repo_root),
            "task_worker_pids": _task_worker_pids(repo_root),
            "screen_session": _screen_has_session("backend-watchdog"),
        },
        "frontend": {
            "port": FRONTEND_PORT,
            "listening": _port_listening(FRONTEND_PORT),
            "http": _http_code(f"http://127.0.0.1:{FRONTEND_PORT}/"),
            "pids": _frontend_pids(repo_root),
        },
    }
    status["ready"] = bool(
        status["postgres"]["accepting"]
        and status["pgbouncer"]["accepting"]
        and status["backend"]["health"].get("ok")
        and status["frontend"]["listening"]
    )
    return status


def start_backend(repo_root: Path, *, with_db: bool = True, wait_seconds: float = 45) -> dict[str, Any]:
    started = time.monotonic()
    steps: list[dict[str, Any]] = []
    if with_db:
        steps.append(ensure_postgres())
        steps.append(ensure_pgbouncer(repo_root))
    script = repo_root / "scripts" / "start_backend.sh"
    if not script.exists():
        return {
            "success": False,
            "status": "error",
            "error": f"start_backend.sh not found: {script}",
            "steps": steps,
            "duration_seconds": round(time.monotonic() - started, 3),
        }
    run = _run(["zsh", str(script)], cwd=repo_root, timeout=max(60, int(wait_seconds) + 30))
    steps.append({"action": "start_backend_script", **run})
    port = _backend_port(repo_root)
    health = _wait_http_health(f"http://127.0.0.1:{port}/api/health", wait_seconds)
    ok = bool(run.get("returncode") == 0 and health.get("ok"))
    return {
        "success": ok,
        "status": "ok" if ok else "error",
        "port": port,
        "health": health,
        "steps": steps,
        "duration_seconds": round(time.monotonic() - started, 3),
        "error": None if ok else "backend start failed or health check did not pass",
    }


def stop_backend(repo_root: Path, *, force: bool = True) -> dict[str, Any]:
    started = time.monotonic()
    killed: dict[str, list[int]] = {
        "watchdog": _terminate_pids(_watchdog_pids(repo_root), force=force),
        "uvicorn": _terminate_pids(_project_uvicorn_pids(repo_root), force=force),
        "task_worker": _terminate_pids(_task_worker_pids(repo_root), force=force),
    }
    # screen session leftover
    if _screen_has_session("backend-watchdog"):
        _run(["screen", "-S", "backend-watchdog", "-X", "quit"], cwd=repo_root, timeout=5)
    for path in (
        repo_root / "backend/logs/.watchdog.lock",
        repo_root / "backend/logs/.watchdog.pid",
    ):
        try:
            if path.is_dir():
                path.rmdir()
            elif path.exists():
                path.unlink()
        except OSError:
            pass
    port = _backend_port(repo_root)
    still = _port_listening(port)
    return {
        "success": not still,
        "status": "ok" if not still else "error",
        "killed": killed,
        "port": port,
        "listening": still,
        "duration_seconds": round(time.monotonic() - started, 3),
        "error": None if not still else f"port {port} still listening",
    }


def start_frontend(repo_root: Path, *, wait_seconds: float = 20) -> dict[str, Any]:
    started = time.monotonic()
    if _port_listening(FRONTEND_PORT):
        return {
            "success": True,
            "status": "already_running",
            "port": FRONTEND_PORT,
            "pids": _frontend_pids(repo_root) or _listen_pids(FRONTEND_PORT),
            "http": _http_code(f"http://127.0.0.1:{FRONTEND_PORT}/"),
            "duration_seconds": round(time.monotonic() - started, 3),
        }
    frontend_dir = repo_root / "frontend"
    log_path = repo_root / "backend" / "logs" / "frontend-dev.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_f = open(log_path, "a", encoding="utf-8")  # noqa: SIM115 — long-lived child inherits handle
    try:
        proc = subprocess.Popen(
            ["npm", "run", "dev"],
            cwd=str(frontend_dir),
            stdout=log_f,
            stderr=subprocess.STDOUT,
            text=True,
            start_new_session=True,
        )
    finally:
        log_f.close()
    deadline = time.monotonic() + max(1.0, wait_seconds)
    while time.monotonic() < deadline:
        if _port_listening(FRONTEND_PORT):
            break
        if proc.poll() is not None:
            break
        time.sleep(0.4)
    listening = _port_listening(FRONTEND_PORT)
    return {
        "success": listening,
        "status": "ok" if listening else "error",
        "pid": proc.pid,
        "port": FRONTEND_PORT,
        "command": "cd frontend && npm run dev",
        "log": str(log_path),
        "http": _http_code(f"http://127.0.0.1:{FRONTEND_PORT}/") if listening else None,
        "returncode": proc.poll(),
        "duration_seconds": round(time.monotonic() - started, 3),
        "error": None if listening else "frontend did not open port 5173",
    }


def stop_frontend(repo_root: Path, *, force: bool = True) -> dict[str, Any]:
    started = time.monotonic()
    pids = sorted(set(_frontend_pids(repo_root) + _listen_pids(FRONTEND_PORT)))
    killed = _terminate_pids(pids, force=force)
    still = _port_listening(FRONTEND_PORT)
    return {
        "success": not still,
        "status": "ok" if not still else "error",
        "killed": killed,
        "port": FRONTEND_PORT,
        "listening": still,
        "duration_seconds": round(time.monotonic() - started, 3),
        "error": None if not still else f"port {FRONTEND_PORT} still listening",
    }


def start_stack(
    repo_root: Path,
    *,
    with_frontend: bool = True,
    wait_seconds: float = 45,
) -> dict[str, Any]:
    started = time.monotonic()
    db_pg = ensure_postgres()
    db_bouncer = ensure_pgbouncer(repo_root)
    backend = start_backend(repo_root, with_db=False, wait_seconds=wait_seconds)
    frontend: dict[str, Any] | None = None
    if with_frontend:
        frontend = start_frontend(repo_root, wait_seconds=min(wait_seconds, 30))
    ok = bool(
        db_pg.get("success")
        and db_bouncer.get("success")
        and backend.get("success")
        and (frontend is None or frontend.get("success"))
    )
    return {
        "success": ok,
        "status": "ok" if ok else "error",
        "postgres": db_pg,
        "pgbouncer": db_bouncer,
        "backend": backend,
        "frontend": frontend,
        "snapshot": service_status(repo_root),
        "duration_seconds": round(time.monotonic() - started, 3),
        "urls": {
            "frontend": "http://localhost:5173",
            "backend_health": f"http://127.0.0.1:{_backend_port(repo_root)}/api/health",
        },
    }


def stop_stack(repo_root: Path, *, stop_db: bool = False, force: bool = True) -> dict[str, Any]:
    started = time.monotonic()
    frontend = stop_frontend(repo_root, force=force)
    backend = stop_backend(repo_root, force=force)
    pgbouncer: dict[str, Any] | None = None
    postgres: dict[str, Any] | None = None
    if stop_db:
        pgbouncer = stop_pgbouncer(repo_root, force=force)
        postgres = stop_postgres(force=force)
    ok = bool(frontend.get("success") and backend.get("success"))
    if stop_db:
        ok = ok and bool(pgbouncer and pgbouncer.get("success") and postgres and postgres.get("success"))
    return {
        "success": ok,
        "status": "ok" if ok else "error",
        "frontend": frontend,
        "backend": backend,
        "pgbouncer": pgbouncer,
        "postgres": postgres,
        "snapshot": service_status(repo_root),
        "duration_seconds": round(time.monotonic() - started, 3),
    }


def restart_backend(
    repo_root: Path,
    *,
    with_db: bool = True,
    force_restart: bool = False,
    wait_seconds: float = 45,
) -> dict[str, Any]:
    started = time.monotonic()
    steps: list[dict[str, Any]] = []
    if with_db:
        steps.append(ensure_postgres())
        steps.append(ensure_pgbouncer(repo_root))
    script = repo_root / "scripts" / "start_backend.sh"
    if not script.exists():
        return {
            "success": False,
            "status": "error",
            "error": f"start_backend.sh not found: {script}",
            "steps": steps,
            "duration_seconds": round(time.monotonic() - started, 3),
        }
    env = os.environ.copy()
    if force_restart:
        env["FORCE_RESTART"] = "1"
    run = _run(
        ["zsh", str(script), "--restart"],
        cwd=repo_root,
        env=env,
        timeout=max(90, int(wait_seconds) + 40),
    )
    steps.append({"action": "restart_backend_script", **run})
    port = _backend_port(repo_root)
    health = _wait_http_health(f"http://127.0.0.1:{port}/api/health", wait_seconds)
    ok = bool(run.get("returncode") == 0 and health.get("ok"))
    return {
        "success": ok,
        "status": "ok" if ok else "error",
        "restarted": run.get("returncode") == 0,
        "port": port,
        "health": health,
        "steps": steps,
        "duration_seconds": round(time.monotonic() - started, 3),
        "error": None if ok else "backend restart failed or health check did not pass",
    }


# ── database helpers ────────────────────────────────────────────────────


def ensure_postgres() -> dict[str, Any]:
    if _pg_isready(POSTGRES_PORT):
        return {
            "success": True,
            "status": "already_running",
            "port": POSTGRES_PORT,
            "action": "ensure_postgres",
        }
    if _FLYENV_PG_START.exists():
        run = _run(["zsh", str(_FLYENV_PG_START)], cwd=_FLYENV_PG_START.parent, timeout=30)
    elif _FLYENV_PG_CTL.exists() and _FLYENV_PG_DATA.exists():
        run = _run(
            [str(_FLYENV_PG_CTL), "-D", str(_FLYENV_PG_DATA), "start"],
            cwd=_FLYENV_PG_DATA,
            timeout=30,
        )
    else:
        return {
            "success": False,
            "status": "error",
            "action": "ensure_postgres",
            "port": POSTGRES_PORT,
            "error": "FlyEnv PostgreSQL start script/data not found",
        }
    ok = _wait_port(POSTGRES_PORT, 20) and _pg_isready(POSTGRES_PORT)
    return {
        "success": ok,
        "status": "ok" if ok else "error",
        "action": "ensure_postgres",
        "port": POSTGRES_PORT,
        "start": run,
        "error": None if ok else "postgres did not become ready",
    }


def stop_postgres(*, force: bool = True) -> dict[str, Any]:
    if not _port_listening(POSTGRES_PORT) and not _pg_isready(POSTGRES_PORT):
        return {"success": True, "status": "already_stopped", "action": "stop_postgres", "port": POSTGRES_PORT}
    if _FLYENV_PG_CTL.exists() and _FLYENV_PG_DATA.exists():
        mode = "fast" if force else "smart"
        run = _run(
            [str(_FLYENV_PG_CTL), "-D", str(_FLYENV_PG_DATA), "-m", mode, "stop"],
            cwd=_FLYENV_PG_DATA,
            timeout=30,
        )
    else:
        pids = _listen_pids(POSTGRES_PORT)
        killed = _terminate_pids(pids, force=force)
        still = _port_listening(POSTGRES_PORT)
        return {
            "success": not still,
            "status": "ok" if not still else "error",
            "action": "stop_postgres",
            "port": POSTGRES_PORT,
            "killed": killed,
            "error": None if not still else "postgres still listening",
        }
    still = _port_listening(POSTGRES_PORT)
    return {
        "success": not still,
        "status": "ok" if not still else "error",
        "action": "stop_postgres",
        "port": POSTGRES_PORT,
        "stop": run,
        "error": None if not still else "postgres still listening",
    }


def ensure_pgbouncer(repo_root: Path) -> dict[str, Any]:
    if _pg_isready(PGBOUNCER_PORT):
        return {
            "success": True,
            "status": "already_running",
            "port": PGBOUNCER_PORT,
            "action": "ensure_pgbouncer",
        }
    ini = _pgbouncer_ini(repo_root)
    if not ini.exists():
        return {
            "success": False,
            "status": "error",
            "action": "ensure_pgbouncer",
            "error": f"pgbouncer.ini not found: {ini}",
        }
    pid_file = repo_root / "backend/data/config/pgbouncer/pgbouncer.pid"
    if pid_file.exists():
        old = _read_pid_file(pid_file)
        if old and not _pid_alive(old):
            try:
                pid_file.unlink()
            except OSError:
                pass
    pgbouncer_bin = _which("pgbouncer")
    if not pgbouncer_bin:
        return {
            "success": False,
            "status": "error",
            "action": "ensure_pgbouncer",
            "error": "pgbouncer binary not found in PATH",
        }
    run = _run([pgbouncer_bin, "-d", str(ini)], cwd=repo_root, timeout=15)
    ok = _wait_port(PGBOUNCER_PORT, 10) and _pg_isready(PGBOUNCER_PORT)
    return {
        "success": ok,
        "status": "ok" if ok else "error",
        "action": "ensure_pgbouncer",
        "port": PGBOUNCER_PORT,
        "config": str(ini),
        "start": run,
        "error": None if ok else "pgbouncer did not become ready",
    }


def stop_pgbouncer(repo_root: Path, *, force: bool = True) -> dict[str, Any]:
    pid_file = repo_root / "backend/data/config/pgbouncer/pgbouncer.pid"
    pids = []
    pid = _read_pid_file(pid_file)
    if pid:
        pids.append(pid)
    pids.extend(_listen_pids(PGBOUNCER_PORT))
    # only kill pgbouncer processes (avoid accidental kills)
    pids = [p for p in sorted(set(pids)) if _cmdline_contains(p, "pgbouncer")]
    killed = _terminate_pids(pids, force=force)
    if pid_file.exists():
        try:
            pid_file.unlink()
        except OSError:
            pass
    still = _port_listening(PGBOUNCER_PORT)
    return {
        "success": not still,
        "status": "ok" if not still else "error",
        "action": "stop_pgbouncer",
        "port": PGBOUNCER_PORT,
        "killed": killed,
        "error": None if not still else "pgbouncer still listening",
    }


# ── low-level helpers ───────────────────────────────────────────────────


def _pgbouncer_ini(repo_root: Path) -> Path:
    return repo_root / "backend/data/config/pgbouncer/pgbouncer.ini"


def _backend_port(repo_root: Path) -> int:
    port_file = repo_root / "backend/logs/.backend.port"
    if port_file.exists():
        try:
            return int(port_file.read_text(encoding="utf-8").strip() or BACKEND_PORT)
        except (OSError, ValueError):
            return BACKEND_PORT
    return BACKEND_PORT


def _port_listening(port: int, host: str = "127.0.0.1") -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(0.4)
    try:
        return sock.connect_ex((host, port)) == 0
    except OSError:
        return False
    finally:
        sock.close()


def _wait_port(port: int, timeout_seconds: float) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if _port_listening(port):
            return True
        time.sleep(0.3)
    return _port_listening(port)


def _pg_isready(port: int) -> bool:
    bin_path = _which("pg_isready")
    if not bin_path:
        return _port_listening(port)
    run = _run([bin_path, "-h", "127.0.0.1", "-p", str(port)], cwd=Path.cwd(), timeout=5)
    return run.get("returncode") == 0


def _http_health(url: str, timeout: float = 3.0) -> dict[str, Any]:
    try:
        req = urlrequest.Request(url, method="GET")
        with urlrequest.urlopen(req, timeout=timeout) as resp:  # noqa: S310 — local only
            body = resp.read(500).decode("utf-8", errors="replace")
            return {
                "ok": resp.status == 200 and ("ok" in body.lower() or '"success":true' in body.replace(" ", "").lower()),
                "status_code": resp.status,
                "body": body[:300],
            }
    except Exception as exc:  # noqa: BLE001 — surface health errors
        return {"ok": False, "status_code": None, "error": str(exc)}


def _http_code(url: str, timeout: float = 3.0) -> int | None:
    try:
        req = urlrequest.Request(url, method="GET")
        with urlrequest.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            return int(resp.status)
    except urlerror.HTTPError as exc:
        return int(exc.code)
    except Exception:
        return None


def _wait_http_health(url: str, wait_seconds: float) -> dict[str, Any]:
    deadline = time.monotonic() + max(1.0, wait_seconds)
    last: dict[str, Any] = {"ok": False}
    while time.monotonic() < deadline:
        last = _http_health(url)
        if last.get("ok"):
            return last
        time.sleep(0.8)
    return last


def _run(
    cmd: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
    timeout: int = 60,
) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        out = (proc.stdout or "") + (proc.stderr or "")
        return {
            "command": cmd,
            "returncode": proc.returncode,
            "output_tail": out[-2000:],
        }
    except subprocess.TimeoutExpired as exc:
        out = ((exc.stdout or "") if isinstance(exc.stdout, str) else "") + (
            (exc.stderr or "") if isinstance(exc.stderr, str) else ""
        )
        return {
            "command": cmd,
            "returncode": None,
            "timed_out": True,
            "output_tail": out[-2000:],
            "error": f"timeout after {timeout}s",
        }
    except Exception as exc:  # noqa: BLE001
        return {"command": cmd, "returncode": None, "error": str(exc)}


def _which(name: str) -> str | None:
    from shutil import which

    return which(name)


def _read_pid_file(path: Path) -> int | None:
    try:
        text = path.read_text(encoding="utf-8").strip()
        return int(text) if text else None
    except (OSError, ValueError):
        return None


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False


def _listen_pids(port: int) -> list[int]:
    run = _run(["lsof", "-ti", f"tcp:{port}", "-sTCP:LISTEN"], cwd=Path.cwd(), timeout=5)
    if run.get("returncode") not in (0, None):
        # lsof returns 1 when nothing matches
        text = run.get("output_tail") or ""
        if not text.strip():
            return []
    text = run.get("output_tail") or ""
    pids: list[int] = []
    for line in text.splitlines():
        line = line.strip()
        if line.isdigit():
            pids.append(int(line))
    return pids


def _pgrep_f(pattern: str) -> list[int]:
    run = _run(["pgrep", "-f", pattern], cwd=Path.cwd(), timeout=5)
    text = run.get("output_tail") or ""
    return [int(x) for x in text.split() if x.isdigit()]


def _pid_cwd(pid: int) -> str | None:
    run = _run(["lsof", "-a", "-p", str(pid), "-d", "cwd", "-Fn"], cwd=Path.cwd(), timeout=5)
    for line in (run.get("output_tail") or "").splitlines():
        if line.startswith("n"):
            return line[1:]
    return None


def _cmdline(pid: int) -> str:
    run = _run(["ps", "-p", str(pid), "-o", "command="], cwd=Path.cwd(), timeout=5)
    return (run.get("output_tail") or "").strip()


def _cmdline_contains(pid: int, needle: str) -> bool:
    return needle in _cmdline(pid)


def _project_uvicorn_pids(repo_root: Path) -> list[int]:
    backend = str((repo_root / "backend").resolve())
    pids: list[int] = []
    for pid in _pgrep_f("uvicorn app.main:app"):
        cwd = _pid_cwd(pid) or ""
        cmd = _cmdline(pid)
        if backend in cwd or backend in cmd:
            pids.append(pid)
    for pid in _listen_pids(_backend_port(repo_root)):
        cmd = _cmdline(pid)
        if "uvicorn" in cmd or "app.main:app" in cmd:
            pids.append(pid)
    return sorted(set(pids))


def _watchdog_pids(repo_root: Path) -> list[int]:
    script = str((repo_root / "scripts" / "backend_watchdog.sh").resolve())
    pids = []
    for pid in _pgrep_f("backend_watchdog.sh"):
        cmd = _cmdline(pid)
        if script in cmd or "backend_watchdog" in cmd:
            pids.append(pid)
    pid_file = _read_pid_file(repo_root / "backend/logs/.watchdog.pid")
    if pid_file and _pid_alive(pid_file):
        pids.append(pid_file)
    return sorted(set(pids))


def _task_worker_pids(repo_root: Path) -> list[int]:
    backend = str((repo_root / "backend").resolve())
    pids = []
    for pid in _pgrep_f("app.task_worker_main"):
        cwd = _pid_cwd(pid) or ""
        cmd = _cmdline(pid)
        if backend in cwd or backend in cmd or "task_worker_main" in cmd:
            pids.append(pid)
    return sorted(set(pids))


def _frontend_pids(repo_root: Path) -> list[int]:
    frontend = str((repo_root / "frontend").resolve())
    pids: list[int] = []
    for pattern in ("vite", "npm run dev"):
        for pid in _pgrep_f(pattern):
            cwd = _pid_cwd(pid) or ""
            cmd = _cmdline(pid)
            if frontend in cwd or frontend in cmd:
                pids.append(pid)
    return sorted(set(pids))


def _screen_has_session(name: str) -> bool:
    run = _run(["screen", "-ls"], cwd=Path.cwd(), timeout=5)
    text = run.get("output_tail") or ""
    return name in text


def _terminate_pids(pids: list[int], *, force: bool = True, grace_seconds: float = 8.0) -> list[int]:
    killed: list[int] = []
    unique = sorted({p for p in pids if isinstance(p, int) and p > 0})
    for pid in unique:
        try:
            os.kill(pid, signal.SIGTERM)
            killed.append(pid)
        except ProcessLookupError:
            continue
        except PermissionError:
            continue
        except OSError:
            continue
    deadline = time.monotonic() + grace_seconds
    while time.monotonic() < deadline:
        alive = [p for p in unique if _pid_alive(p)]
        if not alive:
            return killed
        time.sleep(0.2)
    if force:
        for pid in unique:
            if not _pid_alive(pid):
                continue
            try:
                os.kill(pid, signal.SIGKILL)
                if pid not in killed:
                    killed.append(pid)
            except ProcessLookupError:
                continue
            except OSError:
                continue
    return killed
