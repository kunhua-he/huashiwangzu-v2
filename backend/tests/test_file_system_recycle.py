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

async def _upload(client, headers, name, content=b"test"):
    resp = await client.post("/api/files/upload", files={"file": (name, content)}, headers=headers)
    return resp.json()["data"]["id"]

async def _del_file(client, headers, fid):
    await client.post("/api/files/delete", json={"type": "file", "id": fid}, headers=headers)
    resp = await client.get("/api/recycle/list", headers=headers)
    for item in resp.json()["data"]:
        if item["origin_id"] == fid:
            await client.post("/api/recycle/delete-permanently", json={"item_type": item["item_type"], "id": item["id"]}, headers=headers)

@pytest.mark.asyncio
async def test_delete_and_restore_file():
    uid = _uid()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": f"Bearer {await _login(client)}"}
        fid = await _upload(client, headers, f"to-delete-{uid}.txt", b"delete me")
        try:
            await client.post("/api/files/delete", json={"type": "file", "id": fid}, headers=headers)
            resp = await client.get("/api/recycle/list", headers=headers)
            rid = next((item["id"] for item in resp.json()["data"] if item["origin_id"] == fid), None)
            assert rid is not None
            resp = await client.post("/api/recycle/restore", json={"item_type": "file", "id": rid}, headers=headers)
            assert resp.json()["success"]
        finally:
            await _del_file(client, headers, fid)

@pytest.mark.asyncio
async def test_permanent_delete():
    uid = _uid()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": f"Bearer {await _login(client)}"}
        fid = await _upload(client, headers, f"perm-delete-{uid}.txt", b"permanent")
        try:
            await client.post("/api/files/delete", json={"type": "file", "id": fid}, headers=headers)
            resp = await client.get("/api/recycle/list", headers=headers)
            rid = next((item["id"] for item in resp.json()["data"] if item["origin_id"] == fid), None)
            assert rid is not None
            resp = await client.post("/api/recycle/delete-permanently", json={"item_type": "file", "id": rid}, headers=headers)
            assert resp.json()["success"]
        finally:
            pass # file already permanently deleted

@pytest.mark.asyncio
async def test_empty_trash():
    uid = _uid()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": f"Bearer {await _login(client)}"}
        fid = await _upload(client, headers, f"empty-test-{uid}.txt", b"empty me")
        await client.post("/api/files/delete", json={"type": "file", "id": fid}, headers=headers)
        resp = await client.post("/api/recycle/empty", headers=headers)
        assert resp.json()["success"]
        resp2 = await client.get("/api/recycle/list", headers=headers)
        assert not any(item["origin_id"] == fid for item in resp2.json()["data"])
