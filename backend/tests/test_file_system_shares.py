import uuid
import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app

SEED_PASS = "admin123"

def _uid():
    return uuid.uuid4().hex[:8]

async def _login(client, username="admin"):
    resp = await client.post("/api/login", json={"username": username, "password": SEED_PASS})
    return resp.json()["data"]["access_token"]

async def _del_file(client, headers, fid):
    await client.post("/api/files/delete", json={"type": "file", "id": fid}, headers=headers)
    resp = await client.get("/api/recycle/list", headers=headers)
    for item in resp.json()["data"]:
        if item["origin_id"] == fid:
            await client.post("/api/recycle/delete-permanently", json={"item_type": item["item_type"], "id": item["id"]}, headers=headers)

@pytest.mark.asyncio
async def test_share_and_check_access():
    uid = _uid()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        ah = {"Authorization": f"Bearer {await _login(client, 'admin')}"}
        vh = {"Authorization": f"Bearer {await _login(client, 'viewer')}"}
        resp = await client.post("/api/files/upload", files={"file": (f"share-me-{uid}.txt", b"shared content")}, headers=ah)
        fid = resp.json()["data"]["id"]
        try:
            resp = await client.get(f"/api/files/share/check/{fid}", headers=vh)
            assert resp.json()["data"]["accessible"] is False
            resp = await client.post("/api/files/share", json={"file_id": fid, "target_user_id": 2, "permission": "read"}, headers=ah)
            assert resp.json()["success"]
            sid = resp.json()["data"]["id"]
            resp = await client.get(f"/api/files/share/check/{fid}", headers=vh)
            assert resp.json()["data"]["accessible"] is True
            assert resp.json()["data"]["permission"] == "read"
            resp = await client.get("/api/files/share/received", headers=vh)
            assert resp.json()["success"]
            resp = await client.get("/api/files/share/sent", headers=ah)
            assert resp.json()["success"]
            resp = await client.delete(f"/api/files/share/{sid}", headers=ah)
            assert resp.json()["success"]
            resp = await client.get(f"/api/files/share/check/{fid}", headers=vh)
            assert resp.json()["data"]["accessible"] is False
        finally:
            await _del_file(client, ah, fid)

@pytest.mark.asyncio
async def test_non_owner_cannot_share():
    uid = _uid()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        ah = {"Authorization": f"Bearer {await _login(client, 'admin')}"}
        vh = {"Authorization": f"Bearer {await _login(client, 'viewer')}"}
        resp = await client.post("/api/files/upload", files={"file": (f"mine-{uid}.txt", b"mine")}, headers=ah)
        fid = resp.json()["data"]["id"]
        try:
            resp = await client.post("/api/files/share", json={"file_id": fid, "target_user_id": 1, "permission": "read"}, headers=vh)
            assert resp.status_code == 403
        finally:
            await _del_file(client, ah, fid)
