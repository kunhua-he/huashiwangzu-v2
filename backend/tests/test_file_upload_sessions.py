"""Chunked upload session tests."""

import hashlib
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from app.database import AsyncSessionLocal
from app.main import app
from app.models.file_upload_session import FileUploadSession
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

SEED_PASS = "admin123"


async def _login(client: AsyncClient, username: str = "admin") -> str:
    resp = await client.post("/api/login", json={"username": username, "password": SEED_PASS})
    return resp.json()["data"]["access_token"]


async def _cleanup_file(client: AsyncClient, headers: dict, file_id: int) -> None:
    await client.post("/api/files/delete", json={"type": "file", "id": file_id}, headers=headers)
    resp = await client.get("/api/recycle/list", headers=headers)
    for item in resp.json()["data"]:
        if item["origin_id"] == file_id:
            await client.post(
                "/api/recycle/delete-permanently",
                json={"item_type": item["item_type"], "id": item["id"]},
                headers=headers,
            )


async def _delete_sessions(*session_ids: str) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(delete(FileUploadSession).where(FileUploadSession.session_id.in_(session_ids)))
        await db.commit()


@pytest.mark.asyncio
async def test_chunked_upload_session_complete_and_download() -> None:
    content_parts = [b"hello ", b"chunked ", b"upload"]
    content = b"".join(content_parts)
    filename = f"upload-session-{uuid4().hex}.txt"
    transport = ASGITransport(app=app)
    session_id = ""
    file_id = 0
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _login(client)
        headers = {"Authorization": f"Bearer {token}"}
        resp = await client.post(
            "/api/files/upload-sessions",
            json={
                "filename": filename,
                "total_chunks": len(content_parts),
                "md5_expected": hashlib.md5(content).hexdigest(),
            },
            headers=headers,
        )
        data = resp.json()
        assert data["success"] is True
        session_id = data["data"]["session_id"]

        for index, chunk in enumerate(content_parts):
            resp = await client.post(
                f"/api/files/upload-sessions/{session_id}/chunks",
                data={"chunk_index": str(index)},
                files={"chunk": (f"{index}.part", chunk, "application/octet-stream")},
                headers=headers,
            )
            data = resp.json()
            assert data["success"] is True
            assert data["data"]["received_chunks"] == index + 1

        resp = await client.post(
            f"/api/files/upload-sessions/{session_id}/complete",
            json={"folder_id": 0, "relative_path": ""},
            headers=headers,
        )
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["session"]["status"] == "completed"
        file_id = data["data"]["file"]["id"]

        resp = await client.get(f"/api/files/download/{file_id}/original", headers=headers)
        assert resp.status_code == 200
        assert resp.content == content

        await _cleanup_file(client, headers, file_id)
    await _delete_sessions(session_id)


@pytest.mark.asyncio
async def test_chunked_upload_session_can_resume_missing_chunk() -> None:
    filename = f"upload-session-resume-{uuid4().hex}.txt"
    transport = ASGITransport(app=app)
    session_id = ""
    file_id = 0
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _login(client)
        headers = {"Authorization": f"Bearer {token}"}
        resp = await client.post(
            "/api/files/upload-sessions",
            json={"filename": filename, "total_chunks": 2},
            headers=headers,
        )
        session_id = resp.json()["data"]["session_id"]

        resp = await client.post(
            f"/api/files/upload-sessions/{session_id}/chunks",
            data={"chunk_index": "0"},
            files={"chunk": ("0.part", b"first-", "application/octet-stream")},
            headers=headers,
        )
        assert resp.json()["success"] is True

        resp = await client.post(
            f"/api/files/upload-sessions/{session_id}/complete",
            json={},
            headers=headers,
        )
        data = resp.json()
        assert resp.status_code == 422
        assert data["success"] is False
        assert "missing" in data["error"].lower()

        resp = await client.post(
            f"/api/files/upload-sessions/{session_id}/chunks",
            data={"chunk_index": "1"},
            files={"chunk": ("1.part", b"second", "application/octet-stream")},
            headers=headers,
        )
        assert resp.json()["success"] is True

        resp = await client.post(
            f"/api/files/upload-sessions/{session_id}/complete",
            json={},
            headers=headers,
        )
        data = resp.json()
        assert data["success"] is True
        file_id = data["data"]["file"]["id"]
        await _cleanup_file(client, headers, file_id)
    await _delete_sessions(session_id)


@pytest.mark.asyncio
async def test_chunked_upload_session_abort_and_cleanup_expired() -> None:
    transport = ASGITransport(app=app)
    aborted_session_id = ""
    expired_session_id = ""
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _login(client)
        headers = {"Authorization": f"Bearer {token}"}

        bad = await client.post(
            "/api/files/upload-sessions",
            json={"filename": "../bad.txt", "total_chunks": 1},
            headers=headers,
        )
        assert bad.status_code == 422
        assert bad.json()["success"] is False

        resp = await client.post(
            "/api/files/upload-sessions",
            json={"filename": f"upload-session-abort-{uuid4().hex}.txt", "total_chunks": 1},
            headers=headers,
        )
        aborted_session_id = resp.json()["data"]["session_id"]
        resp = await client.post(f"/api/files/upload-sessions/{aborted_session_id}/abort", headers=headers)
        assert resp.json()["data"]["status"] == "aborted"

        resp = await client.post(
            "/api/files/upload-sessions",
            json={"filename": f"upload-session-expired-{uuid4().hex}.txt", "total_chunks": 1},
            headers=headers,
        )
        expired_session_id = resp.json()["data"]["session_id"]
        async with AsyncSessionLocal() as db:
            row = (await db.execute(select(FileUploadSession).where(FileUploadSession.session_id == expired_session_id))).scalar_one()
            row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            await db.commit()

        resp = await client.post("/api/files/upload-sessions/cleanup-expired", headers=headers)
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["cleaned"] >= 1

    await _delete_sessions(aborted_session_id, expired_session_id)
