"""Knowledge-module operational diagnostics for the project toolkit."""

from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path
from statistics import median
from typing import Any

TOOL_NAMES = {"knowledge_pipeline_snapshot"}


def tool_definitions() -> list[Any]:
    from mcp.types import Tool

    return [
        Tool(
            name="knowledge_pipeline_snapshot",
            description="汇总知识库管道阶段队列、DB连接状态、最近失败和模型调用日志，用于批量分析巡检。",
            inputSchema={
                "type": "object",
                "properties": {
                    "failed_limit": {"type": "integer", "description": "最近失败任务条数", "default": 20},
                    "log_lines": {
                        "type": "integer",
                        "description": "扫描 backend.log 尾部行数，默认1200；设0跳过日志摘要",
                        "default": 1200,
                    },
                },
            },
        ),
    ]


def handles_tool(name: str) -> bool:
    return name in TOOL_NAMES


async def handle_tool(repo_root: Path, name: str, arguments: dict[str, Any]) -> str:
    if name != "knowledge_pipeline_snapshot":
        raise ValueError(f"未知知识库工具: {name}")
    failed_limit = int(arguments.get("failed_limit", 20) or 20)
    log_lines = int(arguments.get("log_lines", 1200) or 0)
    snapshot = await _db_snapshot(repo_root, failed_limit=max(0, failed_limit))
    snapshot["log_summary"] = _log_summary(repo_root, max(0, log_lines))
    return json.dumps(snapshot, ensure_ascii=False, indent=2)


async def _db_snapshot(repo_root: Path, *, failed_limit: int) -> dict[str, Any]:
    script = """
import asyncio
import json
from sqlalchemy import text
from app.database import AsyncSessionLocal

NAMES = {
    "source_validate": "源文件校验",
    "parse_index": "基础解析/索引",
    "page_render": "页面截图/压缩资产",
    "raw_text": "原始文本采集",
    "raw_ocr": "本地 OCR",
    "raw_vision": "VLM 看图理解",
    "fusion": "LLM 融合交叉印证",
    "profile": "文档画像/标签",
    "graph": "实体图谱抽取",
    "relations": "关系/联动构建",
}
ORDER = list(NAMES)

async def main():
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(text('''
            select stage_key, max(lane_key) lane_key,
                   count(*) filter (where status='pending') pending,
                   count(*) filter (where status='pending' and coalesce(ready_status,'ready')='ready') ready,
                   count(*) filter (where status='running') running,
                   count(*) filter (where status='failed') failed,
                   count(*) filter (where status='completed') completed,
                   count(*) total
            from framework_system_task_queues
            where task_type='kb_pipeline_stage'
            group by stage_key
        '''))).mappings().all()
        db_states = (await db.execute(text('''
            select coalesce(state,'null') state, count(*) count
            from pg_stat_activity
            where datname=current_database()
            group by state order by state
        '''))).mappings().all()
        failures = (await db.execute(text('''
            select id, document_id, stage_key, retry_count, max_retries,
                   left(coalesce(error_message,''), 360) error_message, updated_at
            from framework_system_task_queues
            where task_type='kb_pipeline_stage' and status='failed'
            order by updated_at desc
            limit :limit
        '''), {"limit": FAILED_LIMIT})).mappings().all()

    by_stage = {row["stage_key"]: row for row in rows}
    totals = {"pending": 0, "ready": 0, "running": 0, "failed": 0, "completed": 0, "total": 0}
    stages = []
    for stage in ORDER:
        row = by_stage.get(stage)
        if not row:
            continue
        item = {
            "stage": stage,
            "name": NAMES[stage],
            "lane": row["lane_key"],
            "pending": int(row["pending"]),
            "ready": int(row["ready"]),
            "running": int(row["running"]),
            "failed": int(row["failed"]),
            "completed": int(row["completed"]),
            "total": int(row["total"]),
        }
        item["remaining"] = item["pending"] + item["running"] + item["failed"]
        item["rate"] = round(item["completed"] / item["total"] * 100, 1) if item["total"] else 0.0
        for key in totals:
            totals[key] += item[key]
        stages.append(item)
    totals["remaining"] = totals["pending"] + totals["running"] + totals["failed"]
    totals["rate"] = round(totals["completed"] / totals["total"] * 100, 1) if totals["total"] else 0.0
    print(json.dumps({
        "success": True,
        "stages": stages,
        "totals": totals,
        "db_states": [dict(row) for row in db_states],
        "recent_failures": [{**dict(row), "updated_at": str(row["updated_at"])} for row in failures],
    }, ensure_ascii=False, default=str))

asyncio.run(main())
""".replace("FAILED_LIMIT", str(failed_limit))
    env = os.environ.copy()
    env["PYTHONPATH"] = "backend"
    proc = await asyncio.create_subprocess_exec(
        _project_python(repo_root),
        "-c",
        script,
        cwd=repo_root,
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        return {
            "success": False,
            "error": stderr.decode("utf-8", errors="replace")[-4000:],
        }
    return json.loads(stdout.decode("utf-8"))


def _project_python(repo_root: Path) -> str:
    candidate = repo_root / "backend" / ".venv" / "bin" / "python"
    return str(candidate) if candidate.exists() else "python3"


def _tail_lines(path: Path, max_lines: int) -> list[str]:
    if max_lines <= 0 or not path.exists():
        return []
    try:
        return path.read_text(encoding="utf-8", errors="replace").splitlines()[-max_lines:]
    except OSError:
        return []


def _log_summary(repo_root: Path, log_lines: int) -> dict[str, Any]:
    lines = _tail_lines(repo_root / "backend" / "logs" / "backend.log", log_lines)
    durations: list[int] = []
    summary: dict[str, Any] = {
        "scanned_lines": len(lines),
        "gpt55_success": 0,
        "read_timeout": 0,
        "fallback_succeeded": 0,
        "degraded": 0,
        "vision_failed": 0,
        "errors": 0,
        "recent_error_samples": [],
    }
    for line in lines:
        if "model=gpt-5.5-knowledge" in line and "[USAGE]" in line and "error=" not in line:
            summary["gpt55_success"] += 1
        if "ReadTimeout" in line:
            summary["read_timeout"] += 1
        if "fallback succeeded" in line:
            summary["fallback_succeeded"] += 1
        if "LLM_CALL_DEGRADED" in line or "model_degraded=True" in line:
            summary["degraded"] += 1
        if "Vision model" in line and "failed" in line:
            summary["vision_failed"] += 1
        if " ERROR " in line or "Traceback" in line:
            summary["errors"] += 1
            if len(summary["recent_error_samples"]) < 12:
                summary["recent_error_samples"].append(line[-500:])
        match = re.search(r"duration=(\\d+)ms", line)
        if match:
            durations.append(int(match.group(1)))
    summary["model_duration_ms"] = {
        "count": len(durations),
        "median": int(median(durations)) if durations else None,
        "p90": _percentile(durations, 0.9),
        "max": max(durations) if durations else None,
    }
    return summary


def _percentile(values: list[int], pct: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * pct)))
    return ordered[index]
