from __future__ import annotations

import json
from pathlib import Path

import anyio
import pytest

from dev_toolkit import service_lifecycle_tools as svc


pytest.importorskip("mcp")


def test_service_lifecycle_tools_are_discoverable() -> None:
    tools = {tool.name: tool for tool in svc.tool_definitions()}
    for name in (
        "service_status",
        "start_backend",
        "stop_backend",
        "start_frontend",
        "stop_frontend",
        "start_stack",
        "stop_stack",
        "restart_backend",
    ):
        assert name in tools
        assert svc.handles_tool(name) is True


def test_service_status_aggregates_ports(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(svc, "_port_listening", lambda port, host="127.0.0.1": port in {5432, 6432, 33000})
    monkeypatch.setattr(svc, "_pg_isready", lambda port: port in {5432, 6432})
    monkeypatch.setattr(
        svc,
        "_http_health",
        lambda url, timeout=3.0: {"ok": True, "status_code": 200, "body": '{"success":true}'},
    )
    monkeypatch.setattr(svc, "_http_code", lambda url, timeout=3.0: 200 if "5173" not in url else None)
    monkeypatch.setattr(svc, "_project_uvicorn_pids", lambda repo: [11])
    monkeypatch.setattr(svc, "_watchdog_pids", lambda repo: [12])
    monkeypatch.setattr(svc, "_task_worker_pids", lambda repo: [13])
    monkeypatch.setattr(svc, "_frontend_pids", lambda repo: [])
    monkeypatch.setattr(svc, "_screen_has_session", lambda name: True)
    monkeypatch.setattr(svc, "_backend_port", lambda repo: 33000)

    result = svc.service_status(tmp_path)

    assert result["success"] is True
    assert result["postgres"]["accepting"] is True
    assert result["pgbouncer"]["accepting"] is True
    assert result["backend"]["health"]["ok"] is True
    assert result["frontend"]["listening"] is False
    assert result["ready"] is False


def test_start_frontend_skips_when_port_open(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(svc, "_port_listening", lambda port, host="127.0.0.1": port == 5173)
    monkeypatch.setattr(svc, "_frontend_pids", lambda repo: [99])
    monkeypatch.setattr(svc, "_http_code", lambda url, timeout=3.0: 200)

    result = svc.start_frontend(tmp_path)

    assert result["success"] is True
    assert result["status"] == "already_running"
    assert result["pids"] == [99]


def test_start_stack_orders_db_backend_frontend(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: list[str] = []

    monkeypatch.setattr(
        svc,
        "ensure_postgres",
        lambda: calls.append("postgres") or {"success": True, "status": "ok"},
    )
    monkeypatch.setattr(
        svc,
        "ensure_pgbouncer",
        lambda repo: calls.append("pgbouncer") or {"success": True, "status": "ok"},
    )
    monkeypatch.setattr(
        svc,
        "start_backend",
        lambda repo, with_db=True, wait_seconds=45: calls.append(f"backend:{with_db}")
        or {"success": True, "status": "ok"},
    )
    monkeypatch.setattr(
        svc,
        "start_frontend",
        lambda repo, wait_seconds=20: calls.append("frontend") or {"success": True, "status": "ok"},
    )
    monkeypatch.setattr(
        svc,
        "service_status",
        lambda repo: {"ready": True},
    )
    monkeypatch.setattr(svc, "_backend_port", lambda repo: 33000)

    result = svc.start_stack(tmp_path)

    assert result["success"] is True
    assert calls == ["postgres", "pgbouncer", "backend:False", "frontend"]
    assert result["urls"]["frontend"] == "http://localhost:5173"


def test_handle_tool_service_status(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(svc, "service_status", lambda repo: {"success": True, "ready": False})
    text = anyio.run(svc.handle_tool, tmp_path, "service_status", {})
    payload = json.loads(text)
    assert payload["success"] is True
