from uuid import uuid4

import pytest
from app.main import app
from httpx import ASGITransport, AsyncClient

SEED_PASS = "admin123"

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

async def _del_folder(client, headers, fid):
    await client.post("/api/files/delete", json={"type": "folder", "id": fid}, headers=headers)
    resp = await client.get("/api/recycle/list", headers=headers)
    for item in resp.json()["data"]:
        if item["origin_id"] == fid:
            await client.post("/api/recycle/delete-permanently", json={"item_type": item["item_type"], "id": item["id"]}, headers=headers)

@pytest.mark.asyncio
async def test_delete_and_restore_file():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": f"Bearer {await _login(client)}"}
        fid = await _upload(client, headers, "to-delete.txt", b"delete me")
        await client.post("/api/files/delete", json={"type": "file", "id": fid}, headers=headers)
        resp = await client.get("/api/recycle/list", headers=headers)
        rid = next((item["id"] for item in resp.json()["data"] if item["origin_id"] == fid), None)
        assert rid is not None
        resp = await client.post("/api/recycle/restore", json={"item_type": "file", "id": rid}, headers=headers)
        assert resp.json()["success"]
        await _del_file(client, headers, fid)

@pytest.mark.asyncio
async def test_permanent_delete():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": f"Bearer {await _login(client)}"}
        fid = await _upload(client, headers, "perm-delete.txt", b"permanent")
        await client.post("/api/files/delete", json={"type": "file", "id": fid}, headers=headers)
        resp = await client.get("/api/recycle/list", headers=headers)
        rid = next((item["id"] for item in resp.json()["data"] if item["origin_id"] == fid), None)
        assert rid is not None
        resp = await client.post("/api/recycle/delete-permanently", json={"item_type": "file", "id": rid}, headers=headers)
        assert resp.json()["success"]

@pytest.mark.asyncio
async def test_empty_trash():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": f"Bearer {await _login(client)}"}
        resp = await client.post("/api/recycle/empty", headers=headers)
        assert resp.json()["success"]

@pytest.mark.asyncio
async def test_viewer_can_restore_and_permanently_delete_own_file():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": f"Bearer {await _login(client, 'viewer')}"}
        fid = await _upload(client, headers, f"viewer-recycle-{uuid4().hex}.txt", b"viewer recycle")

        resp = await client.post("/api/files/delete", json={"type": "file", "id": fid}, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["success"] is True

        resp = await client.get("/api/recycle/list", headers=headers)
        rid = next((item["id"] for item in resp.json()["data"] if item["origin_id"] == fid), None)
        assert rid is not None

        resp = await client.post("/api/recycle/restore", json={"item_type": "file", "id": rid}, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["success"] is True

        resp = await client.post("/api/files/delete", json={"type": "file", "id": fid}, headers=headers)
        assert resp.status_code == 200

        resp = await client.get("/api/recycle/list", headers=headers)
        rid = next((item["id"] for item in resp.json()["data"] if item["origin_id"] == fid), None)
        assert rid is not None

        resp = await client.post(
            "/api/recycle/delete-permanently",
            json={"item_type": "file", "id": rid},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True


@pytest.mark.asyncio
async def test_permanent_delete_duplicate_recycled_file_keeps_other_blob():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": f"Bearer {await _login(client)}"}
        marker = uuid4().hex
        content = f"same-content-{marker}".encode()
        fid_one = await _upload(client, headers, f"dupe-one-{marker}.txt", content)
        fid_two = await _upload(client, headers, f"dupe-two-{marker}.txt", content)

        await client.post("/api/files/delete", json={"type": "file", "id": fid_one}, headers=headers)
        await client.post("/api/files/delete", json={"type": "file", "id": fid_two}, headers=headers)
        resp = await client.get("/api/recycle/list", headers=headers)
        recycle_items = resp.json()["data"]
        rid_one = next(item["id"] for item in recycle_items if item["origin_id"] == fid_one)
        rid_two = next(item["id"] for item in recycle_items if item["origin_id"] == fid_two)

        resp = await client.post(
            "/api/recycle/delete-permanently",
            json={"item_type": "file", "id": rid_one},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

        resp = await client.post(
            "/api/recycle/restore",
            json={"item_type": "file", "id": rid_two},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

        resp = await client.get(f"/api/files/download/{fid_two}/original", headers=headers)
        assert resp.status_code == 200
        assert resp.content == content

        await _del_file(client, headers, fid_two)
