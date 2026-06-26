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

async def _del_folder(client, headers, fid):
    await client.post("/api/files/delete", json={"type": "folder", "id": fid}, headers=headers)
    resp = await client.get("/api/recycle/list", headers=headers)
    for item in resp.json()["data"]:
        if item["origin_id"] == fid:
            await client.post("/api/recycle/delete-permanently", json={"item_type": item["item_type"], "id": item["id"]}, headers=headers)

@pytest.mark.asyncio
async def test_rename_file():
    uid = _uid()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": f"Bearer {await _login(client)}"}
        fid = await _upload(client, headers, f"oldname-{uid}.txt")
        try:
            await client.post("/api/files/rename", json={"type": "file", "id": fid, "new_name": f"newname-{uid}"}, headers=headers)
            resp = await client.get("/api/files/list?folder_id=0", headers=headers)
            found = any(item["id"] == fid and item["name"] == f"newname-{uid}" for item in resp.json()["data"]["items"])
            assert found
        finally:
            await _del_file(client, headers, fid)

@pytest.mark.asyncio
async def test_move_file():
    uid = _uid()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": f"Bearer {await _login(client)}"}
        fr = await client.post("/api/files/folder", json={"name": f"move-target-{uid}"}, headers=headers)
        folder_id = fr.json()["data"]["id"]
        try:
            fid = await _upload(client, headers, f"moveme-{uid}.txt")
            await client.post("/api/files/move", json={"type": "file", "id": fid, "target_folder_id": folder_id}, headers=headers)
        finally:
            await _del_file(client, headers, fid)
            await _del_folder(client, headers, folder_id)

@pytest.mark.asyncio
async def test_copy_file():
    uid = _uid()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": f"Bearer {await _login(client)}"}
        fid = await _upload(client, headers, f"copyme-{uid}.txt", b"content")
        try:
            resp = await client.post("/api/files/copy", json={"type": "file", "id": fid, "target_folder_id": None}, headers=headers)
            assert resp.json()["success"]
            cid = resp.json()["data"]["id"]
            assert cid != fid
        finally:
            await _del_file(client, headers, fid)
            await _del_file(client, headers, cid)

@pytest.mark.asyncio
async def test_copy_file_to_root_with_zero_folder_id():
    uid = _uid()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": f"Bearer {await _login(client)}"}
        fid = await _upload(client, headers, f"copyroot-{uid}.txt", b"root copy")
        try:
            resp = await client.post("/api/files/copy", json={"type": "file", "id": fid, "target_folder_id": 0}, headers=headers)
            assert resp.json()["success"]
            cid = resp.json()["data"]["id"]
            assert cid != fid
            list_resp = await client.get("/api/files/list?folder_id=0", headers=headers)
            copied = [item for item in list_resp.json()["data"]["items"] if item["id"] == cid]
            assert copied and copied[0]["parent_id"] is None
        finally:
            await _del_file(client, headers, fid)
            await _del_file(client, headers, cid)
