# -*- coding: utf-8 -*-
"""Knowledge pipeline pause/resume control for MCP (quota-wait gate)."""
from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_BURN_STAGES = ("raw_ocr", "raw_vision", "fusion", "profile", "graph")
STAGE_CONCURRENCY_KEYS = {
    "raw_ocr": ("raw_ocr",),
    "raw_vision": ("raw_vision",),
    "fusion": ("fusion", "page_fusion"),
    "profile": ("profile",),
    "graph": ("graph", "entity_extract"),
}


def task_worker_path(repo_root: Path) -> Path:
    return repo_root / "backend" / "data" / "config" / "task_worker.json"


def models_config_path(repo_root: Path) -> Path:
    return repo_root / "backend" / "data" / "config" / "models.json"


def project_python(repo_root: Path) -> str:
    candidate = repo_root / "backend" / ".venv" / "bin" / "python"
    return str(candidate) if candidate.exists() else "python3"


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def read_json_dict(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def normalize_stage_list(value: Any, default: list[str] | tuple[str, ...] = ()) -> list[str]:
    if value is None:
        items = list(default)
    elif isinstance(value, str):
        items = [part.strip() for part in value.replace(";", ",").split(",") if part.strip()]
    elif isinstance(value, (list, tuple, set)):
        items = [str(item).strip() for item in value if str(item).strip()]
    else:
        items = list(default)
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


async def run_project_python_json(repo_root: Path, script: str) -> dict[str, Any]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(repo_root / "backend")
    proc = await asyncio.create_subprocess_exec(
        project_python(repo_root),
        "-c",
        script,
        cwd=str(repo_root),
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        err = (stderr.decode("utf-8", errors="replace") or stdout.decode("utf-8", errors="replace"))[:2000]
        return {"success": False, "error": err, "returncode": proc.returncode}
    text_out = stdout.decode("utf-8", errors="replace").strip()
    if not text_out:
        return {"success": False, "error": "empty python output"}
    try:
        data = json.loads(text_out.splitlines()[-1])
    except json.JSONDecodeError:
        return {"success": False, "error": f"invalid json output: {text_out[:500]}"}
    if isinstance(data, dict):
        data.setdefault("success", True)
        return data
    return {"success": True, "data": data}


async def queue_stage_counts(repo_root: Path, stages: list[str]) -> dict[str, Any]:
    stages = normalize_stage_list(stages)
    stages_json = json.dumps(stages, ensure_ascii=False)
    script = f"""
import asyncio, json
from sqlalchemy import text
from app.database import AsyncSessionLocal
STAGES = json.loads({json.dumps(stages_json)})
async def main():
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(text(
            "SELECT stage_key, status, count(*)::int AS c "
            "FROM framework_system_task_queues "
            "WHERE stage_key = ANY(:stages) "
            "GROUP BY stage_key, status ORDER BY stage_key, status"
        ), {{"stages": STAGES}})).mappings().all()
        out = {{}}
        for row in rows:
            out.setdefault(row["stage_key"], {{}})[row["status"]] = int(row["c"])
        missing = (await db.execute(text(
            "SELECT count(*)::int AS c FROM kb_documents d "
            "WHERE d.graph_status = 'pending' AND COALESCE(d.deleted, false) = false "
            "AND NOT EXISTS ("
            "  SELECT 1 FROM framework_system_task_queues q "
            "  WHERE q.document_id = d.id AND q.stage_key = 'graph' "
            "    AND q.status IN ('pending','running')"
            ")"
        ))).scalar()
        print(json.dumps({{"by_stage": out, "graph_missing_queue": int(missing or 0)}}, ensure_ascii=False))
asyncio.run(main())
"""
    return await run_project_python_json(repo_root, script)


async def pipeline_control(repo_root: Path, arguments: dict[str, Any]) -> dict[str, Any]:
    action = str(arguments.get("action") or "status").strip().lower()
    if action not in {"status", "pause", "resume"}:
        return {"success": False, "error": f"unsupported action: {action}"}

    tw_path = task_worker_path(repo_root)
    models_path = models_config_path(repo_root)
    tw = read_json_dict(tw_path)
    models = read_json_dict(models_path)
    knowledge = ((models.get("module_routing") or {}).get("knowledge") or {})
    concurrency = knowledge.get("pipeline_concurrency") if isinstance(knowledge, dict) else {}
    if not isinstance(concurrency, dict):
        concurrency = {}
    paused_map = tw.get("paused_stages") if isinstance(tw.get("paused_stages"), dict) else {}
    current_paused = [str(x) for x in (paused_map.get("kb_pipeline_stage") or []) if str(x).strip()]
    requested_stages = normalize_stage_list(arguments.get("stages"))
    reason = str(arguments.get("reason") or "").strip()
    confirm = str(arguments.get("confirm") or "").strip()

    if action == "status":
        stages_for_q = sorted(set(current_paused) | set(DEFAULT_BURN_STAGES) | set(requested_stages))
        queue = await queue_stage_counts(repo_root, stages_for_q)
        return {
            "success": True,
            "action": "status",
            "paused_stages": current_paused,
            "manual_hold": bool((tw.get("model_auto_pause") or {}).get("manual_hold")),
            "model_auto_pause": tw.get("model_auto_pause") or {},
            "pipeline_concurrency": {
                k: concurrency.get(k)
                for k in (
                    "raw_ocr",
                    "raw_vision",
                    "fusion",
                    "page_fusion",
                    "profile",
                    "graph",
                    "entity_extract",
                    "model_call_global",
                )
            },
            "stages_routing": (knowledge.get("stages") if isinstance(knowledge, dict) else {}),
            "queue": queue,
            "hold_policy": "额度等待期间默认禁止自动跑模型；resume 需 CONFIRM_RESUME",
        }

    if action == "pause":
        stages = requested_stages or list(DEFAULT_BURN_STAGES)
        set_zero = arguments.get("set_concurrency_zero", True)
        if isinstance(set_zero, str):
            set_zero = set_zero.strip().lower() not in {"0", "false", "no"}
        paused_set = set(current_paused) | set(stages)
        tw["paused_stages"] = {"kb_pipeline_stage": sorted(paused_set)}
        tw["model_auto_pause"] = {
            "enabled": False,
            "manual_hold": True,
            "reason": reason or "manual_pause_via_mcp",
            "paused_stages": sorted(paused_set),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "note": "人工额度等待闸门；只能用 knowledge_pipeline_control action=resume + CONFIRM_RESUME 开启",
        }
        concurrency_updates: dict[str, int] = {}
        if set_zero:
            knowledge = dict(knowledge) if isinstance(knowledge, dict) else {}
            pc = dict(concurrency)
            for stage in stages:
                for key in STAGE_CONCURRENCY_KEYS.get(stage, (stage,)):
                    pc[key] = 0
                    concurrency_updates[key] = 0
            knowledge["pipeline_concurrency"] = pc
            module_routing = dict(models.get("module_routing") or {})
            module_routing["knowledge"] = knowledge
            models["module_routing"] = module_routing
            atomic_write_json(models_path, models)
        atomic_write_json(tw_path, tw)
        queue = await queue_stage_counts(repo_root, sorted(paused_set))
        return {
            "success": True,
            "action": "pause",
            "paused_stages": sorted(paused_set),
            "concurrency_set_zero": concurrency_updates,
            "reason": reason or "manual_pause_via_mcp",
            "queue": queue,
            "running_policy": "dispatcher 不再领取这些 stage；已 running 会在心跳后被 paused_by_config 释放",
        }

    if confirm != "CONFIRM_RESUME":
        return {
            "success": False,
            "action": "resume",
            "error": "resume 需要 confirm=CONFIRM_RESUME（防误开额度）",
            "current_paused_stages": current_paused,
        }
    stages = requested_stages or [s for s in current_paused if s in DEFAULT_BURN_STAGES] or list(current_paused)
    if not stages:
        return {
            "success": False,
            "action": "resume",
            "error": "没有可恢复的 paused stages；可传 stages=[...]",
            "current_paused_stages": current_paused,
        }
    remaining = [s for s in current_paused if s not in set(stages)]
    tw["paused_stages"] = {"kb_pipeline_stage": remaining} if remaining else {}
    tw["model_auto_pause"] = {
        "enabled": False,
        "manual_hold": False,
        "cleared_at": datetime.now(timezone.utc).isoformat(),
        "cleared_reason": reason or "manual_resume_via_mcp",
        "cleared_stages": stages,
        "note": "已由 MCP 手动恢复",
    }
    concurrency_arg = arguments.get("concurrency") or {}
    concurrency_updates: dict[str, int] = {}
    if isinstance(concurrency_arg, dict) and concurrency_arg:
        knowledge = dict(knowledge) if isinstance(knowledge, dict) else {}
        pc = dict(concurrency)
        for key, value in concurrency_arg.items():
            try:
                iv = int(value)
            except (TypeError, ValueError):
                continue
            pc[str(key)] = max(0, iv)
            concurrency_updates[str(key)] = max(0, iv)
        knowledge["pipeline_concurrency"] = pc
        module_routing = dict(models.get("module_routing") or {})
        module_routing["knowledge"] = knowledge
        models["module_routing"] = module_routing
        atomic_write_json(models_path, models)
    atomic_write_json(tw_path, tw)
    queue = await queue_stage_counts(
        repo_root,
        sorted(set(stages) | set(remaining) | set(DEFAULT_BURN_STAGES)),
    )
    return {
        "success": True,
        "action": "resume",
        "resumed_stages": stages,
        "still_paused_stages": remaining,
        "concurrency_updates": concurrency_updates,
        "reason": reason or "manual_resume_via_mcp",
        "queue": queue,
        "note": "若 concurrency 仍为 0，worker 可能仍不实质推进；请在 concurrency 参数里显式给 graph/entity_extract 等正数",
    }
