import json

import pytest
from app.database import AsyncSessionLocal
from sqlalchemy import delete, select

from modules.agent.backend.models import ApprovalQueue
from modules.agent.backend.services.action_policy import _match_sensitive, check_action_allowed


@pytest.mark.parametrize("tool_name", ["terminal-tools__exec", "terminal-tools__execute"])
def test_terminal_execute_names_are_sensitive(tool_name: str) -> None:
    assert _match_sensitive(tool_name) is True


@pytest.mark.asyncio
async def test_approval_queue_stores_redacted_tool_args() -> None:
    agent_code = "test_action_policy_args"
    tool_args = {
        "name": "terminal-tools__exec",
        "args": {
            "command": "echo hello",
            "cwd": "data/workspaces/42",
            "token": "super-secret-token",
            "nested": {"api_key": "key-123", "path": "notes/report.md"},
            "long_text": "x" * 2500,
        },
    }

    async with AsyncSessionLocal() as db:
        try:
            result = await check_action_allowed(
                db,
                "terminal-tools__exec",
                agent_code,
                user_id=42,
                conversation_id=9001,
                tool_args=tool_args,
            )
            assert result["allowed"] is False
            assert result["action"] == "confirm"

            row = await db.scalar(
                select(ApprovalQueue).where(ApprovalQueue.id == result["approval_id"])
            )
            assert row is not None
            assert row.tool_args
            assert row.tool_args != ""

            saved_args = json.loads(row.tool_args)
            assert saved_args["name"] == "terminal-tools__exec"
            assert saved_args["args"]["command"] == "echo hello"
            assert saved_args["args"]["cwd"] == "data/workspaces/42"
            assert saved_args["args"]["token"] == "[REDACTED]"
            assert saved_args["args"]["nested"]["api_key"] == "[REDACTED]"
            assert saved_args["args"]["nested"]["path"] == "notes/report.md"
            assert len(saved_args["args"]["long_text"]) < 2500
            assert "truncated" in saved_args["args"]["long_text"]
        finally:
            await db.execute(delete(ApprovalQueue).where(ApprovalQueue.agent_code == agent_code))
            await db.commit()
