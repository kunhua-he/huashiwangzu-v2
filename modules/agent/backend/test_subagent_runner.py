"""Regression tests for subagent runner ownership context."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@pytest.mark.asyncio
async def test_subagent_skill_describe_receives_owner_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from modules.agent.backend.services import subagent_runner

    captured_owner_ids: list[int | None] = []
    call_count = 0

    async def fake_chat(**kwargs: object) -> dict:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return {
                "content": "",
                "tool_calls": [{
                    "id": "call_1",
                    "type": "function",
                    "function": {
                        "name": "skill_describe",
                        "arguments": json.dumps({"name": "knowledge__search"}),
                    },
                }],
            }
        return {"content": "done", "tool_calls": []}

    async def fake_handle_skill_describe(
        params: dict,
        role: str,
        owner_id: int | None = None,
        agent_code: str = "default",
    ) -> dict:
        captured_owner_ids.append(owner_id)
        return {"name": params["name"], "agent_code": agent_code}

    monkeypatch.setattr(subagent_runner.gateway_router, "chat", fake_chat)
    monkeypatch.setattr(
        subagent_runner.tool_discovery,
        "handle_skill_describe",
        fake_handle_skill_describe,
    )

    result = await subagent_runner._execute_tool_loop(
        messages=[{"role": "system", "content": "test"}],
        task_tools=[],
        max_rounds=2,
        task_write_enabled=False,
        caller="user:55",
        caller_role="viewer",
        owner_id=55,
        task_desc="describe a skill",
    )

    assert result["status"] == "completed"
    assert result["conclusion"] == "done"
    assert captured_owner_ids == [55]
