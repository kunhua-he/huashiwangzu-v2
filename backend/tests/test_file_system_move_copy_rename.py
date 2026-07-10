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
async def test_rename_file():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": f"Bearer {await _login(client)}"}
        fid = await _upload(client, headers, "oldname.txt")
        await client.post("/api/files/rename", json={"type": "file", "id": fid, "new_name": "newname"}, headers=headers)
        resp = await client.get("/api/files/list?folder_id=0", headers=headers)
        found = any(item["id"] == fid and item["name"] == "newname" for item in resp.json()["data"]["items"])
        assert found
        await _del_file(client, headers, fid)

@pytest.mark.asyncio
async def test_move_file():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": f"Bearer {await _login(client)}"}
        fr = await client.post("/api/files/folder", json={"name": "move-target"}, headers=headers)
        folder_id = fr.json()["data"]["id"]
        fid = await _upload(client, headers, "moveme.txt")
        await client.post("/api/files/move", json={"type": "file", "id": fid, "target_folder_id": folder_id}, headers=headers)
        await _del_file(client, headers, fid)
        await _del_folder(client, headers, folder_id)

@pytest.mark.asyncio
async def test_copy_file():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": f"Bearer {await _login(client)}"}
        fid = await _upload(client, headers, "copyme.txt", b"content")
        resp = await client.post("/api/files/copy", json={"type": "file", "id": fid, "target_folder_id": None}, headers=headers)
        assert resp.json()["success"]
        cid = resp.json()["data"]["id"]
        assert cid != fid
        await _del_file(client, headers, fid)
        await _del_file(client, headers, cid)

@pytest.mark.asyncio
async def test_copy_file_to_root_with_zero_folder_id():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": f"Bearer {await _login(client)}"}
        fid = await _upload(client, headers, "copyroot.txt", b"root copy")
        resp = await client.post("/api/files/copy", json={"type": "file", "id": fid, "target_folder_id": 0}, headers=headers)
        assert resp.json()["success"]
        cid = resp.json()["data"]["id"]
        assert cid != fid
        list_resp = await client.get("/api/files/list?folder_id=0", headers=headers)
        copied = [item for item in list_resp.json()["data"]["items"] if item["id"] == cid]
        assert copied and copied[0]["parent_id"] is None
        await _del_file(client, headers, fid)
        await _del_file(client, headers, cid)

@pytest.mark.asyncio
async def test_viewer_can_manage_own_uploaded_file():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": f"Bearer {await _login(client, 'viewer')}"}
        folder_name = f"viewer-manage-{uuid4().hex}"
        fr = await client.post("/api/files/folder", json={"name": folder_name}, headers=headers)
        assert fr.status_code == 200
        folder_id = fr.json()["data"]["id"]

        fid = await _upload(client, headers, f"viewer-manage-{uuid4().hex}.txt", b"viewer owns this")
        resp = await client.post(
            "/api/files/rename",
            json={"type": "file", "id": fid, "new_name": f"viewer-renamed-{uuid4().hex}"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

        resp = await client.post(
            "/api/files/move",
            json={"type": "file", "id": fid, "target_folder_id": folder_id},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

        resp = await client.post(
            "/api/files/copy",
            json={"type": "file", "id": fid, "target_folder_id": None},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        cid = resp.json()["data"]["id"]

        resp = await client.post("/api/files/delete", json={"type": "file", "id": fid}, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["success"] is True

        await _del_file(client, headers, cid)
        await _del_folder(client, headers, folder_id)
