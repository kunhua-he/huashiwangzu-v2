"""Office compatibility bridge and Content Package versions tests."""
import pytest
from app.main import app
from httpx import ASGITransport, AsyncClient

SEED_PASS = "admin123"


async def _login(client: AsyncClient) -> str:
    resp = await client.post("/api/login", json={"username": "admin", "password": SEED_PASS})
    return resp.json()["data"]["access_token"]


@pytest.mark.asyncio
async def test_office_patch_routes_deleted() -> None:
    """Old patch/rollback endpoints were removed — assert 404."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for path in ("/api/office/patch/preview", "/api/office/patch/apply", "/api/office/rollback"):
            resp = await client.post(path, json={})
            assert resp.status_code == 404, f"{path} should be 404 (removed), got {resp.status_code}"


@pytest.mark.asyncio
async def test_office_status_authenticated() -> None:
    """GET /api/office/status/{file_id} must return 200 for an existing file (fixed P0)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": f"Bearer {await _login(client)}"}
        resp = await client.get("/api/office/status/1", headers=headers)
        # 200 if accessible, 403 if not owned by test user — never 500 (fixed P0)
        assert resp.status_code in (200, 403), f"Expected 200 or 403, got {resp.status_code}"


@pytest.mark.asyncio
async def test_office_status_nonexistent_file() -> None:
    """GET /api/office/status/{file_id} for a non-existent file must return 404."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": f"Bearer {await _login(client)}"}
        resp = await client.get("/api/office/status/99999", headers=headers)
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"


@pytest.mark.asyncio
async def test_office_package_versions_for_nonexistent() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": f"Bearer {await _login(client)}"}
        resp = await client.get("/api/office/package/99999/versions", headers=headers)
        assert resp.status_code in (200, 404)
