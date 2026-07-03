from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import anyio

from dev_toolkit.agent_board_tools import (
    block_task,
    claim_task,
    complete_task,
    heartbeat_task,
    read_board,
    snapshot,
    tool_definitions,
    write_board,
)


def _load(raw: str) -> dict:
    data = json.loads(raw)
    assert isinstance(data, dict)
    return data


def test_agent_board_claim_heartbeat_complete_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "agent_board.json"

    async def run() -> None:
        claimed = _load(
            await claim_task(
                path,
                agent="devtool-agent-board-r5",
                title="Durable board",
                objective="persist subagent progress",
                labels="devtool,mcp",
                node_note="node 1 claimed",
            )
        )
        assert claimed["success"] is True
        assert claimed["created"] is True
        task_id = claimed["task"]["task_id"]
        assert claimed["task"]["status"] == "claimed"
        assert claimed["task"]["owner_agent"] == "devtool-agent-board-r5"
        assert claimed["task"]["node_log"][0]["note"] == "node 1 claimed"

        heartbeat = _load(
            await heartbeat_task(
                path,
                agent="devtool-agent-board-r5",
                task_id=task_id,
                node_note="node 2 still working",
            )
        )
        assert heartbeat["success"] is True
        assert heartbeat["task"]["node_log"][-1]["action"] == "heartbeat"

        completed = _load(
            await complete_task(
                path,
                agent="devtool-agent-board-r5",
                task_id=task_id,
                result_summary="implemented",
            )
        )
        assert completed["success"] is True
        assert completed["task"]["status"] == "completed"
        assert completed["summary"]["completed"] == 1

        board = read_board(path)
        assert len(board["events"]) == 3

    anyio.run(run)


def test_agent_board_rejects_fresh_claim_and_non_owner_terminal_state(tmp_path: Path) -> None:
    path = tmp_path / "agent_board.json"

    async def run() -> None:
        first = _load(await claim_task(path, agent="agent-a", task_id="shared-task", title="Shared"))
        assert first["success"] is True

        second = _load(await claim_task(path, agent="agent-b", task_id="shared-task", title="Shared"))
        assert second["success"] is False
        assert second["rejected"] is True
        assert second["task"]["owner_agent"] == "agent-a"

        blocked = _load(await block_task(path, agent="agent-b", task_id="shared-task", reason="not owner"))
        assert blocked["success"] is False
        assert blocked["rejected"] is True

    anyio.run(run)


def test_agent_board_heartbeat_missing_task_points_to_claim(tmp_path: Path) -> None:
    path = tmp_path / "agent_board.json"

    async def run() -> None:
        heartbeat = _load(
            await heartbeat_task(
                path,
                agent="agent-a",
                task_id="missing-task",
                node_note="node 1",
            )
        )
        assert heartbeat["success"] is False
        assert heartbeat["error"] == "task not found"
        assert "agent_board_claim" in heartbeat["hint"]
        assert heartbeat["claim_example"]["agent"] == "agent-a"
        assert heartbeat["claim_example"]["task_id"] == "missing-task"

    anyio.run(run)


def test_agent_board_allows_stale_reclaim_and_records_block(tmp_path: Path) -> None:
    path = tmp_path / "agent_board.json"

    async def run() -> None:
        claimed = _load(await claim_task(path, agent="agent-a", task_id="stale-task", title="Stale"))
        task = claimed["task"]
        board = read_board(path)
        old = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        board["tasks"][task["task_id"]]["heartbeat_at"] = old
        write_board(path, board)

        reclaimed = _load(
            await claim_task(
                path,
                agent="agent-b",
                task_id="stale-task",
                title="Stale",
                stale_after_seconds=10,
                node_note="take over stale work",
            )
        )
        assert reclaimed["success"] is True
        assert reclaimed["created"] is False
        assert reclaimed["task"]["owner_agent"] == "agent-b"

        blocked = _load(await block_task(path, agent="agent-b", task_id="stale-task", reason="external blocker"))
        assert blocked["success"] is True
        assert blocked["task"]["status"] == "blocked"
        assert blocked["task"]["block_reason"] == "external blocker"

        board_view = _load(await snapshot(path, status="blocked", include_events=True))
        assert board_view["summary"]["blocked"] == 1
        assert board_view["tasks"][0]["task_id"] == "stale-task"
        assert board_view["events"][-1]["action"] == "block"

    anyio.run(run)


def test_agent_board_tool_contract_names() -> None:
    names = {tool.name for tool in tool_definitions()}
    assert names == {
        "agent_board_claim",
        "agent_board_heartbeat",
        "agent_board_complete",
        "agent_board_block",
        "agent_board_snapshot",
    }


def test_agent_board_snapshot_reports_corrupt_file(tmp_path: Path) -> None:
    path = tmp_path / "agent_board.json"
    path.write_text("{not-json", encoding="utf-8")

    async def run() -> None:
        board_view = _load(await snapshot(path))
        assert board_view["success"] is False
        assert "Failed to read agent board" in board_view["error"]

    anyio.run(run)


def test_agent_board_claim_backs_up_corrupt_file_before_recovery(tmp_path: Path) -> None:
    path = tmp_path / "agent_board.json"
    path.write_text("{not-json", encoding="utf-8")

    async def run() -> None:
        claimed = _load(await claim_task(path, agent="agent-a", task_id="recover-task", title="Recover"))
        assert claimed["success"] is True
        board = read_board(path)
        assert "recovered_from_corrupt" in board
        assert board["events"][0]["action"] == "recover_corrupt_board"
        backup_path = Path(board["recovered_from_corrupt"])
        assert backup_path.exists()
        assert backup_path.read_text(encoding="utf-8") == "{not-json"

    anyio.run(run)
