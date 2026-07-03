"""Private module lifecycle must match its router state."""

import shutil
from pathlib import Path
from uuid import uuid4

import pytest
from app.database import AsyncSessionLocal
from app.main import app
from app.models.private_module import PrivateModule
from app.services import private_module_service as pms
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

SEED_PASS = "admin123"


async def _login(client: AsyncClient) -> str:
    resp = await client.post("/api/login", json={"username": "admin", "password": SEED_PASS})
    return resp.json()["data"]["access_token"]


async def _cleanup_private_module(owner_id: int, module_key: str, data_root: Path) -> None:
    pms._unregister_private_module(owner_id, module_key, "/api/private/1/probe-private")
    async with AsyncSessionLocal() as db:
        await db.execute(delete(PrivateModule).where(PrivateModule.module_key == module_key))
        await db.commit()
    shutil.rmtree(data_root, ignore_errors=True)


def _write_private_module(root: Path, owner_id: int, module_key: str) -> None:
    module_dir = root / "workspaces" / str(owner_id) / "private_modules" / module_key
    backend_dir = module_dir / "backend"
    backend_dir.mkdir(parents=True, exist_ok=True)
    (module_dir / "manifest.json").write_text(
        (
            "{"
            f"\"key\":\"{module_key}\","
            f"\"name\":\"{module_key}\","
            "\"module_version\":\"1.0.0\","
            "\"route_prefix\":\"/probe-private\","
            "\"backend\":{\"enabled\":true,\"router\":\"backend/router.py\"}"
            "}"
        ),
        encoding="utf-8",
    )
    (backend_dir / "router.py").write_text(
        (
            "from fastapi import APIRouter\n"
            "router = APIRouter()\n"
            "@router.get('/ping')\n"
            "async def ping():\n"
            "    return {'ok': True}\n"
        ),
        encoding="utf-8",
    )


@pytest.mark.asyncio
async def test_private_module_deactivate_removes_runtime_route(monkeypatch, tmp_path) -> None:
    owner_id = 1
    module_key = f"pm_{uuid4().hex}"
    data_root = tmp_path / "private-module-lifecycle"
    workspace_root = data_root / "workspaces"
    install_root = data_root / "installed"
    monkeypatch.setattr(pms, "WORKSPACES_ROOT", workspace_root)
    monkeypatch.setattr(pms, "PRIVATE_MODULES_INSTALL_ROOT", install_root)
    pms.set_app_instance(app)
    _write_private_module(data_root, owner_id, module_key)

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            token = await _login(client)
            headers = {"Authorization": f"Bearer {token}"}

            install_resp = await client.post(
                "/api/private-modules/install",
                json={"module_key": module_key},
                headers=headers,
            )
            assert install_resp.json()["success"] is True

            activate_resp = await client.post(f"/api/private-modules/{module_key}/activate", headers=headers)
            activate_data = activate_resp.json()
            assert activate_data["success"] is True
            assert activate_data["data"]["status"] == "active"
            assert activate_data["data"]["router_prefix"] == "/api/private/1/probe-private"

            unauth_resp = await client.get("/api/private/1/probe-private/ping")
            assert unauth_resp.status_code in {401, 403}

            route_resp = await client.get("/api/private/1/probe-private/ping", headers=headers)
            assert route_resp.status_code == 200
            assert route_resp.json() == {"ok": True}

            deactivate_resp = await client.post(f"/api/private-modules/{module_key}/deactivate", headers=headers)
            assert deactivate_resp.json()["success"] is True

            removed_resp = await client.get("/api/private/1/probe-private/ping", headers=headers)
            assert removed_resp.status_code == 404

            uninstall_resp = await client.delete(f"/api/private-modules/{module_key}", headers=headers)
            assert uninstall_resp.json()["success"] is True
    finally:
        await _cleanup_private_module(owner_id, module_key, data_root)


@pytest.mark.asyncio
async def test_private_module_activation_failure_rolls_back_runtime_route(monkeypatch, tmp_path) -> None:
    owner_id = 1
    module_key = f"pm_{uuid4().hex}"
    data_root = tmp_path / "private-module-activation-failure"
    workspace_root = data_root / "workspaces"
    install_root = data_root / "installed"
    monkeypatch.setattr(pms, "WORKSPACES_ROOT", workspace_root)
    monkeypatch.setattr(pms, "PRIVATE_MODULES_INSTALL_ROOT", install_root)
    pms.set_app_instance(app)
    _write_private_module(data_root, owner_id, module_key)

    original_refresh = pms._refresh_middleware_stack

    def fail_refresh(_app: object) -> None:
        raise RuntimeError("simulated middleware refresh failure")

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            token = await _login(client)
            headers = {"Authorization": f"Bearer {token}"}

            install_resp = await client.post(
                "/api/private-modules/install",
                json={"module_key": module_key},
                headers=headers,
            )
            assert install_resp.json()["success"] is True

            monkeypatch.setattr(pms, "_refresh_middleware_stack", fail_refresh)
            activate_resp = await client.post(f"/api/private-modules/{module_key}/activate", headers=headers)
            activate_data = activate_resp.json()
            assert activate_data["success"] is False
            assert "simulated middleware refresh failure" in activate_data["error"]
            assert activate_data["data"]["status"] == "failed"
            assert "simulated middleware refresh failure" in activate_data["data"]["error_message"]

            monkeypatch.setattr(pms, "_refresh_middleware_stack", original_refresh)
            original_refresh(app)
            route_resp = await client.get("/api/private/1/probe-private/ping", headers=headers)
            assert route_resp.status_code == 404

            uninstall_resp = await client.delete(f"/api/private-modules/{module_key}", headers=headers)
            assert uninstall_resp.json()["success"] is True
    finally:
        await _cleanup_private_module(owner_id, module_key, data_root)
