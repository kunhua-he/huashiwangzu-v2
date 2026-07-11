from __future__ import annotations

import pytest
from app.services import system_status_service, task_worker


@pytest.mark.asyncio
async def test_external_worker_mode_is_healthy_when_web_worker_is_idle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TASK_WORKER_AUTOSTART", "0")
    monkeypatch.setattr(task_worker, "worker_health", lambda: {"running": False})

    result = await system_status_service.check_worker()

    assert result == {
        "status": True,
        "message": "Background worker uses external watchdog supervision",
    }


@pytest.mark.asyncio
async def test_in_process_worker_mode_reports_stopped_worker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TASK_WORKER_AUTOSTART", "1")
    monkeypatch.setattr(task_worker, "worker_health", lambda: {"running": False})

    result = await system_status_service.check_worker()

    assert result == {
        "status": False,
        "message": "Background worker is not running",
    }
