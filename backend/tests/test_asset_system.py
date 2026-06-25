"""Tests for the Agent asset system (FileAsset model + API)."""
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

SEED_PASS = "admin123"


async def _login(client: AsyncClient) -> str:
    resp = await client.post("/api/login", json={"username": "admin", "password": SEED_PASS})
    data = resp.json()
    assert data["success"] is True
    return data["data"]["access_token"]


async def _upload_file(client: AsyncClient, headers: dict) -> int:
    resp = await client.post(
        "/api/files/upload",
        files={"file": ("asset_test.txt", b"hello asset system", "text/plain")},
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
    """Test creating an asset record via API."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _login(client)
        headers = {"Authorization": f"Bearer {token}"}
        file_id = await _upload_file(client, headers)

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

        await _cleanup_file(client, headers, file_id)


@pytest.mark.asyncio
async def test_asset_publish_api():
    """Test publishing an asset via API."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _login(client)
        headers = {"Authorization": f"Bearer {token}"}
        file_id = await _upload_file(client, headers)

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

        await _cleanup_file(client, headers, file_id)


@pytest.mark.asyncio
async def test_asset_list_api():
    """Test listing user assets."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _login(client)
        headers = {"Authorization": f"Bearer {token}"}
        file_id = await _upload_file(client, headers)

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

        await _cleanup_file(client, headers, file_id)


@pytest.mark.asyncio
async def test_asset_by_conversation_api():
    """Test listing assets by conversation."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _login(client)
        headers = {"Authorization": f"Bearer {token}"}
        file_id = await _upload_file(client, headers)

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

        await _cleanup_file(client, headers, file_id)


@pytest.mark.asyncio
async def test_asset_delete_api():
    """Test deleting an asset label (not the underlying file)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _login(client)
        headers = {"Authorization": f"Bearer {token}"}
        file_id = await _upload_file(client, headers)

        create_resp = await client.post(
            "/api/assets/create",
            params={"file_id": file_id, "asset_type": "draft"},
            headers=headers,
        )
        asset_id = create_resp.json()["data"]["id"]

        del_resp = await client.delete(f"/api/assets/{asset_id}", headers=headers)
        assert del_resp.json()["success"] is True

        await _cleanup_file(client, headers, file_id)


@pytest.mark.asyncio
async def test_asset_semantic_types():
    """Verify all 5 asset semantic types can be created."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _login(client)
        headers = {"Authorization": f"Bearer {token}"}
        file_id = await _upload_file(client, headers)

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

        await _cleanup_file(client, headers, file_id)


@pytest.mark.asyncio
async def test_asset_invalid_type_rejected():
    """Test invalid asset type is rejected."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _login(client)
        headers = {"Authorization": f"Bearer {token}"}
        file_id = await _upload_file(client, headers)

        resp = await client.post(
            "/api/assets/create",
            params={"file_id": file_id, "asset_type": "invalid_type"},
            headers=headers,
        )
        assert resp.status_code >= 400

        await _cleanup_file(client, headers, file_id)
