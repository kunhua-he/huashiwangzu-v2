from __future__ import annotations

import json
import subprocess
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


def test_agent_board_snapshot_includes_conductor_summary(tmp_path: Path) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True, text=True)
    path = tmp_path / "backend" / "logs" / "agent_board.json"
    memory_dir = tmp_path / "开发文档" / "项目记忆"
    memory_dir.mkdir(parents=True)
    (memory_dir / "r6-worker.md").write_text(
        '---\nname: "R6 worker done"\nagent: "agent-a"\ncreated: "2026-07-03T12:00:00+00:00"\n---\n\n完成。',
        encoding="utf-8",
    )
    (tmp_path / "dev_toolkit").mkdir()
    (tmp_path / "dev_toolkit" / "agent_board_tools.py").write_text("# dirty\n", encoding="utf-8")

    async def run() -> None:
        claimed = _load(await claim_task(path, agent="agent-a", task_id="lane-a", title="Lane A"))
        completed = _load(await claim_task(path, agent="agent-b", task_id="lane-b", title="Lane B"))
        assert completed["success"] is True
        await complete_task(path, agent="agent-b", task_id="lane-b", result_summary="ready to stage")

        board = read_board(path)
        old = (datetime.now(timezone.utc) - timedelta(minutes=40)).isoformat()
        board["tasks"][claimed["task"]["task_id"]]["heartbeat_at"] = old
        write_board(path, board)

        board_view = _load(
            await snapshot(
                path,
                repo_root=tmp_path,
                include_events=False,
                stale_after_seconds=60,
                memory_limit=3,
            )
        )
        conductor = board_view["conductor"]
        assert conductor["lanes"]["claimed"]["count"] == 1
        assert conductor["lanes"]["completed"]["tasks"][0]["result_summary"] == "ready to stage"
        assert conductor["stale_tasks"][0]["task_id"] == "lane-a"
        assert conductor["recent_memory_links"][0]["path"] == "开发文档/项目记忆/r6-worker.md"
        assert "dev_toolkit" in conductor["stage_plan"]["grouped_pathspecs"]
        assert any(command.startswith("git add -- ") for command in conductor["stage_plan"]["suggested_git_add"])

    anyio.run(run)


def test_agent_board_tool_contract_names() -> None:
    tools = tool_definitions()
    names = {tool.name for tool in tools}
    assert names == {
        "agent_board_claim",
        "agent_board_heartbeat",
        "agent_board_complete",
        "agent_board_block",
        "agent_board_snapshot",
    }
    snapshot_tool = next(tool for tool in tools if tool.name == "agent_board_snapshot")
    properties = snapshot_tool.inputSchema["properties"]
    assert "include_conductor" in properties
    assert "stale_after_seconds" in properties
    assert "memory_limit" in properties


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
