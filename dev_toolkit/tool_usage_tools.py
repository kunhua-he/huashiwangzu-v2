"""Tool usage telemetry component for the project toolkit MCP server."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TOOL_NAMES = {"tool_usage_stats"}


def empty_tool_usage() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": None,
        "total_calls": 0,
        "tools": {},
        "agents": {},
        "recent_calls": [],
    }


def read_tool_usage(path: Path) -> dict[str, Any]:
    if not path.exists():
        return empty_tool_usage()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return empty_tool_usage()
    if not isinstance(data, dict):
        return empty_tool_usage()
    data.setdefault("schema_version", 1)
    data.setdefault("created_at", datetime.now(timezone.utc).isoformat())
    data.setdefault("updated_at", None)
    data.setdefault("total_calls", 0)
    data.setdefault("tools", {})
    data.setdefault("agents", {})
    data.setdefault("recent_calls", [])
    return data


def write_tool_usage(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def _infer_agent(arguments: dict[str, Any] | None) -> str:
    if not isinstance(arguments, dict):
        return "unknown"
    for key in ("agent", "caller_agent", "executed_by"):
        value = arguments.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "unknown"


def record_tool_usage(
    path: Path,
    name: str,
    success: bool,
    duration_seconds: float,
    arguments: dict[str, Any] | None = None,
) -> None:
    try:
        data = read_tool_usage(path)
        now = datetime.now(timezone.utc).isoformat()
        agent = _infer_agent(arguments)
        tools = data.setdefault("tools", {})
        item = tools.setdefault(
            name,
            {
                "calls": 0,
                "success": 0,
                "error": 0,
                "total_duration_seconds": 0.0,
                "last_called_at": None,
                "last_success": None,
            },
        )
        item["calls"] = int(item.get("calls", 0)) + 1
        item["success" if success else "error"] = int(item.get("success" if success else "error", 0)) + 1
        item["total_duration_seconds"] = round(float(item.get("total_duration_seconds", 0.0)) + duration_seconds, 3)
        item["last_called_at"] = now
        item["last_success"] = success

        agents = data.setdefault("agents", {})
        agent_item = agents.setdefault(
            agent,
            {
                "calls": 0,
                "success": 0,
                "error": 0,
                "tools": {},
                "last_called_at": None,
            },
        )
        agent_item["calls"] = int(agent_item.get("calls", 0)) + 1
        agent_item["success" if success else "error"] = int(agent_item.get("success" if success else "error", 0)) + 1
        agent_item["last_called_at"] = now
        agent_tools = agent_item.setdefault("tools", {})
        agent_tools[name] = int(agent_tools.get(name, 0)) + 1

        recent = data.setdefault("recent_calls", [])
        recent.append(
            {
                "tool": name,
                "agent": agent,
                "success": success,
                "duration_seconds": round(duration_seconds, 3),
                "called_at": now,
            }
        )
        data["recent_calls"] = recent[-200:]
        data["total_calls"] = int(data.get("total_calls", 0)) + 1
        data["updated_at"] = now
        write_tool_usage(path, data)
    except Exception:
        # Usage telemetry must never break the actual development tool call.
        pass


async def tool_usage_stats(repo_root: Path, usage_path: Path, limit: int = 20, reset: bool = False, confirm: str = "") -> str:
    if reset:
        if confirm != "RESET":
            return json.dumps({"success": False, "error": "reset requires confirm='RESET'"}, ensure_ascii=False, indent=2)
        write_tool_usage(usage_path, empty_tool_usage())
    data = read_tool_usage(usage_path)
    tools = data.get("tools", {})
    ranked = sorted(
        (
            {
                "tool": name,
                "calls": int(item.get("calls", 0)),
                "success": int(item.get("success", 0)),
                "error": int(item.get("error", 0)),
                "total_duration_seconds": float(item.get("total_duration_seconds", 0.0)),
                "avg_duration_seconds": round(
                    float(item.get("total_duration_seconds", 0.0)) / max(int(item.get("calls", 0)), 1),
                    3,
                ),
                "last_called_at": item.get("last_called_at"),
                "last_success": item.get("last_success"),
            }
            for name, item in tools.items()
        ),
        key=lambda item: (-item["calls"], item["tool"]),
    )
    payload = {
        "success": True,
        "stats_path": str(usage_path.relative_to(repo_root)),
        "created_at": data.get("created_at"),
        "updated_at": data.get("updated_at"),
        "total_calls": data.get("total_calls", 0),
        "top_tool": ranked[0] if ranked else None,
        "tools": ranked[: max(limit, 1)],
        "agents": data.get("agents", {}),
        "recent_calls": data.get("recent_calls", [])[-max(limit, 1):],
        "agent_attribution_note": "Per-agent usage is best-effort; tools without an agent/caller_agent argument are recorded as unknown.",
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def tool_definitions() -> list[Any]:
    from mcp.types import Tool

    return [
        Tool(
            name="tool_usage_stats",
            description="统计项目工具台 MCP 工具调用热度，返回调用最多的工具、成功/失败次数、平均耗时；可 confirm=RESET 重置。",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {"type": "number", "description": "返回前 N 个工具", "default": 20},
                    "reset": {"type": "boolean", "description": "是否重置统计", "default": False},
                    "confirm": {"type": "string", "description": "reset=true 时必须传 RESET", "default": ""},
                },
            },
        ),
    ]


def handles_tool(name: str) -> bool:
    return name in TOOL_NAMES


async def handle_tool(repo_root: Path, usage_path: Path, name: str, arguments: dict[str, Any]) -> str:
    if name == "tool_usage_stats":
        return await tool_usage_stats(
            repo_root,
            usage_path,
            limit=int(arguments.get("limit", 20)),
            reset=bool(arguments.get("reset", False)),
            confirm=arguments.get("confirm", ""),
        )
    raise ValueError(f"未知工具统计工具: {name}")
