"""Tests for the Agent asset system (FileAsset model + API)."""
import uuid
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

SEED_PASS = "admin123"


def _uid() -> str:
    return uuid.uuid4().hex[:8]


async def _login(client: AsyncClient) -> str:
    resp = await client.post("/api/login", json={"username": "admin", "password": SEED_PASS})
    data = resp.json()
    assert data["success"] is True
    return data["data"]["access_token"]


async def _upload_file(client: AsyncClient, headers: dict, uid: str) -> int:
    resp = await client.post(
        "/api/files/upload",
        files={"file": (f"asset_test_{uid}.txt", b"hello asset system", "text/plain")},
        data={"folder_id": "0"},
        headers=headers,
    )
    data = resp.json()
    assert data["success"] is True
    return data["data"]["id"]


async def _cleanup_file(client: AsyncClient, headers: dict, file_id: int):
    await client.post("/api/files/delete", json={"type": "file", "id": file_id}, headers=headers)


@pytest.mark.asyncio
async def test_create_asset_api():
    uid = _uid()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _login(client)
        headers = {"Authorization": f"Bearer {token}"}
        file_id = await _upload_file(client, headers, uid)
        try:
            resp = await client.post(
                "/api/assets/create",
                params={"file_id": file_id, "asset_type": "generated", "tool_name": "office-gen__docx"},
                headers=headers,
            )
            data = resp.json()
            assert data["success"] is True, f"Create asset failed: {data}"
            assert data["data"]["asset_type"] == "generated"
            assert data["data"]["file_id"] == file_id
            assert data["data"]["publish_state"] == "draft"
        finally:
            await _cleanup_file(client, headers, file_id)


@pytest.mark.asyncio
async def test_asset_publish_api():
    uid = _uid()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _login(client)
        headers = {"Authorization": f"Bearer {token}"}
        file_id = await _upload_file(client, headers, uid)
        try:
            create_resp = await client.post(
                "/api/assets/create",
                params={"file_id": file_id, "asset_type": "generated"},
                headers=headers,
            )
            asset_id = create_resp.json()["data"]["id"]

            pub_resp = await client.patch(f"/api/assets/{asset_id}/publish", headers=headers)
            pub_data = pub_resp.json()
            assert pub_data["success"] is True
            assert pub_data["data"]["publish_state"] == "published"
        finally:
            await _cleanup_file(client, headers, file_id)


@pytest.mark.asyncio
async def test_asset_list_api():
    uid = _uid()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _login(client)
        headers = {"Authorization": f"Bearer {token}"}
        file_id = await _upload_file(client, headers, uid)
        try:
            await client.post(
                "/api/assets/create",
                params={"file_id": file_id, "asset_type": "generated", "tool_name": "test_tool"},
                headers=headers,
            )

            resp = await client.get("/api/assets", headers=headers)
            data = resp.json()
            assert data["success"] is True
            items = data["data"]["items"]
            assert len(items) >= 1
            assert any(i["tool_name"] == "test_tool" for i in items)

            resp_type = await client.get("/api/assets?asset_type=generated", headers=headers)
            typed = resp_type.json()
            assert all(i["asset_type"] == "generated" for i in typed["data"]["items"])
        finally:
            await _cleanup_file(client, headers, file_id)


@pytest.mark.asyncio
async def test_asset_by_conversation_api():
    uid = _uid()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _login(client)
        headers = {"Authorization": f"Bearer {token}"}
        file_id = await _upload_file(client, headers, uid)
        try:
            await client.post(
                "/api/assets/create",
                params={
                    "file_id": file_id,
                    "asset_type": "generated",
                    "conversation_id": 777,
                    "tool_name": "office-gen__docx",
                },
                headers=headers,
            )

            resp = await client.get("/api/assets/by-conversation/777", headers=headers)
            data = resp.json()
            assert data["success"] is True
            assert len(data["data"]["items"]) >= 1
            assert data["data"]["items"][0]["conversation_id"] == 777
        finally:
            await _cleanup_file(client, headers, file_id)


@pytest.mark.asyncio
async def test_asset_delete_api():
    uid = _uid()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _login(client)
        headers = {"Authorization": f"Bearer {token}"}
        file_id = await _upload_file(client, headers, uid)
        try:
            create_resp = await client.post(
                "/api/assets/create",
                params={"file_id": file_id, "asset_type": "draft"},
                headers=headers,
            )
            asset_id = create_resp.json()["data"]["id"]

            del_resp = await client.delete(f"/api/assets/{asset_id}", headers=headers)
            assert del_resp.json()["success"] is True
        finally:
            await _cleanup_file(client, headers, file_id)


@pytest.mark.asyncio
async def test_asset_semantic_types():
    uid = _uid()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _login(client)
        headers = {"Authorization": f"Bearer {token}"}
        file_id = await _upload_file(client, headers, uid)
        try:
            for atype in ("draft", "published", "evidence", "generated", "handoff"):
                resp = await client.post(
                    "/api/assets/create",
                    params={"file_id": file_id, "asset_type": atype},
                    headers=headers,
                )
                assert resp.json()["success"] is True, f"Failed to create asset type={atype}"
                created_id = resp.json()["data"]["id"]

                resp2 = await client.patch(
                    f"/api/assets/{created_id}/state",
                    params={"asset_type": atype},
                    headers=headers,
                )
                assert resp2.json()["success"] is True
        finally:
            await _cleanup_file(client, headers, file_id)


@pytest.mark.asyncio
async def test_asset_invalid_type_rejected():
    uid = _uid()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _login(client)
        headers = {"Authorization": f"Bearer {token}"}
        file_id = await _upload_file(client, headers, uid)
        try:
            resp = await client.post(
                "/api/assets/create",
                params={"file_id": file_id, "asset_type": "invalid_type"},
                headers=headers,
            )
            assert resp.status_code >= 400
        finally:
            await _cleanup_file(client, headers, file_id)
