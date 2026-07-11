from types import SimpleNamespace

import pytest

from app.routers import logs
from app.schemas.system import FrontendErrorRequest


@pytest.mark.asyncio
async def test_frontend_error_log_allows_anonymous_report(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict] = []

    async def fake_write_log(*args, **kwargs):
        calls.append({"args": args, "kwargs": kwargs})

    monkeypatch.setattr(logs, "write_log", fake_write_log)

    response = await logs.report_frontend_error(
        FrontendErrorRequest(
            url="/api/files/list",
            status_code=401,
            error_message="Authentication required",
            page_path="/desktop",
        ),
        db=object(),
        current_user=None,
    )

    assert response.data == {"ok": True}
    assert calls
    assert calls[0]["args"][1:5] == ("warning", "frontend", "frontend_error", "Authentication required")
    assert calls[0]["kwargs"]["user_id"] == 0
    assert calls[0]["kwargs"]["data"]["status_code"] == 401


@pytest.mark.asyncio
async def test_frontend_error_log_keeps_user_id_when_authenticated(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict] = []

    async def fake_write_log(*args, **kwargs):
        calls.append({"args": args, "kwargs": kwargs})

    monkeypatch.setattr(logs, "write_log", fake_write_log)

    response = await logs.report_frontend_error(
        FrontendErrorRequest(error_message="boom"),
        db=object(),
        current_user=SimpleNamespace(id=7),
    )

    assert response.data == {"ok": True}
    assert calls[0]["kwargs"]["user_id"] == 7
