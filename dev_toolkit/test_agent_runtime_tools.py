from __future__ import annotations

from dev_toolkit import agent_runtime_tools


def test_agent_runtime_snapshot_tool_contract() -> None:
    tools = agent_runtime_tools.tool_definitions()

    assert {tool.name for tool in tools} == {"agent_runtime_snapshot"}
    assert agent_runtime_tools.handles_tool("agent_runtime_snapshot") is True


def test_agent_runtime_snapshot_prioritizes_observed_flow_failures() -> None:
    result = agent_runtime_tools._summarize_snapshot(
        {
            "conversations": [{"id": 1}],
            "trajectories": [
                {
                    "error_occurred": True,
                    "tool_calls": [
                        {"function": {"name": "skill_list"}},
                        {"function": {"name": "skill_describe"}},
                        {"function": {"name": "desktop-tools__read_file"}},
                    ],
                    "tool_results": [
                        {
                            "name": "desktop-tools__read_file",
                            "result": {"error": "Unsupported file extension for reading: .jpg"},
                        },
                    ],
                },
            ],
            "failure_groups": [
                {
                    "tool_name": "knowledge__search",
                    "error_signature": "工具 knowledge__search 在 18 秒内没有返回，已停止等待。",
                    "count": 4,
                },
            ],
            "checkpoints": [],
            "samples": [],
        },
        owner_id=4,
        days=30,
        sample_limit=12,
    )

    issue_keys = {item["key"] for item in result["issues"]}
    assert result["summary"]["meta_tool_calls"] == 2
    assert result["summary"]["capability_calls"] == 1
    assert {"image_routed_to_text_reader", "knowledge_search_timeout"}.issubset(issue_keys)


def test_agent_runtime_snapshot_audits_checkpoint_security_and_recovery() -> None:
    result = agent_runtime_tools._summarize_snapshot(
        {
            "conversations": [],
            "trajectories": [],
            "failure_groups": [],
            "samples": [],
            "checkpoints": [
                {
                    "conversation_id": 7,
                    "owner_id": 4,
                    "channel_values": {
                        "capability_catalog": {
                            "catalog_hash": "a" * 64,
                            "principal": {"user_id": 9},
                        },
                        "action_plan_checkpoint": {
                            "plan": {"catalog_hash": "b" * 64},
                            "observations": {
                                "a1": {"state": "running", "references": []},
                                "a2": {
                                    "state": "completed",
                                    "references": [{"type": "file", "id": ""}],
                                },
                            },
                        },
                    },
                },
            ],
        },
        owner_id=4,
        days=30,
        sample_limit=12,
    )

    health = result["checkpoint_health"]
    assert health["stale_snapshot_count"] == 1
    assert health["permission_leakage_count"] == 1
    assert health["incomplete_reference_count"] == 1
    assert health["interrupted_running_count"] == 1
    assert {
        "stale_snapshot",
        "permission_leakage",
        "resource_ref_incomplete",
        "checkpoint_recovery_pending",
    } <= {item["key"] for item in result["issues"]}
