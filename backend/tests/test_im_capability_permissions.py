from uuid import uuid4

import pytest
from app.database import AsyncSessionLocal
from app.main import app
from app.services.module_registry import call_capability
from httpx import ASGITransport, AsyncClient
from huashiwangzu_modules.im.models import ImConversation, ImMessage, ImReadState
from sqlalchemy import delete, func, select

SEED_PASS = "admin123"


async def _login(client: AsyncClient, username: str) -> tuple[str, int]:
    response = await client.post(
        "/api/login",
        json={"username": username, "password": SEED_PASS},
    )
    response.raise_for_status()
    data = response.json()["data"]
    return data["access_token"], int(data["user"]["id"])


async def _cleanup_im_messages(marker: str) -> None:
    async with AsyncSessionLocal() as db:
        message_result = await db.execute(
            select(ImMessage.id, ImMessage.conversation_id).where(
                ImMessage.content.contains(marker)
            )
        )
        rows = message_result.all()
        message_ids = [row.id for row in rows]
        conversation_ids = [row.conversation_id for row in rows]
        if message_ids:
            await db.execute(delete(ImMessage).where(ImMessage.id.in_(message_ids)))
        if conversation_ids:
            await db.execute(
                delete(ImReadState).where(ImReadState.conversation_id.in_(conversation_ids))
            )
            await db.execute(
                delete(ImConversation).where(ImConversation.id.in_(conversation_ids))
            )
        await db.commit()


@pytest.mark.asyncio
async def test_im_send_capability_requires_conversation_membership() -> None:
    marker = f"im-capability-permission-{uuid4().hex}"
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            editor_token, editor_id = await _login(client, "editor")
            viewer_token, _viewer_id = await _login(client, "viewer")
            editor_headers = {
                "Authorization": f"Bearer {editor_token}",
            }
            viewer_headers = {
                "Authorization": f"Bearer {viewer_token}",
            }

            response = await client.post(
                "/api/im/messages",
                json={
                    "target_user_id": 900_000_000 + editor_id,
                    "content": f"{marker}-http-create",
                },
                headers=editor_headers,
            )
            assert response.status_code == 200
            conversation_id = response.json()["data"]["conversation_id"]

            response = await client.post(
                "/api/modules/call",
                json={
                    "target_module": "im",
                    "action": "send",
                    "parameters": {
                        "conversation_id": conversation_id,
                        "content": f"{marker}-denied",
                    },
                },
                headers=viewer_headers,
            )
            assert response.status_code == 403
            assert "无权向该会话发消息" in response.json()["error"]

            response = await client.post(
                "/api/modules/call",
                json={
                    "target_module": "im",
                    "action": "send",
                    "parameters": {
                        "conversation_id": conversation_id,
                        "content": f"{marker}-member-send",
                    },
                },
                headers=editor_headers,
            )
            assert response.status_code == 200
            assert response.json()["data"]["success"] is True
            assert isinstance(response.json()["data"]["message_id"], int)

            async with AsyncSessionLocal() as db:
                denied_count = await db.scalar(
                    select(func.count()).select_from(ImMessage).where(
                        ImMessage.content == f"{marker}-denied"
                    )
                )
            assert denied_count == 0

            notify_result = await call_capability(
                "im",
                "notify",
                {
                    "user_id": 910_000_000 + editor_id,
                    "content": f"{marker}-system-notify",
                    "title": "IM permission regression",
                },
                caller="system:task-worker",
                caller_role="viewer",
            )
            assert notify_result["success"] is True
            assert isinstance(notify_result["message_id"], int)
    finally:
        await _cleanup_im_messages(marker)
