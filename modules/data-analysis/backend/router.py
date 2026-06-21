"""FastAPI router for data-analysis module.

Exposes 2 cross-module capabilities:
  data-analysis:run    — Execute Python code (pandas/numpy/matplotlib) in subprocess
  data-analysis:chart  — Simplified chart generation via matplotlib
"""

import io
import os
import sys
import json
import uuid
import shutil
import logging
import subprocess
from pathlib import Path

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, AsyncSessionLocal
from app.middleware.auth import require_permission
from app.models.user import User
from app.schemas.common import ApiResponse
from app.services.module_registry import register_capability
from app.config import get_settings
from app.core.exceptions import NotFound, AppException

logger = logging.getLogger("v2.data-analysis")

router = APIRouter(prefix="/api/data-analysis", tags=["data-analysis"])

_MAX_OUTPUT_BYTES = 1 * 1024 * 1024
_DEFAULT_TIMEOUT = 60
_MAX_TIMEOUT = 600
_CHART_EXTENSIONS = {".png", ".jpg", ".jpeg", ".svg"}

_WORKSPACE_ROOT: Path | None = None


def _get_workspace_base() -> Path:
    global _WORKSPACE_ROOT
    if _WORKSPACE_ROOT is None:
        settings = get_settings()
        base = Path(settings.UPLOAD_DIR).resolve().parent
        _WORKSPACE_ROOT = (base / "workspaces").resolve()
        _WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)
    return _WORKSPACE_ROOT


def _resolve_user_id(caller: str) -> int:
    if caller.startswith("user:"):
        try:
            return int(caller.split(":", 1)[1])
        except ValueError:
            pass
    raise ValueError(f"Unknown caller format: {caller}")


def _user_workspace(user_id: int) -> Path:
    ws = _get_workspace_base() / str(user_id)
    ws.mkdir(parents=True, exist_ok=True)
    return ws


def _resolve_workspace_path(user_id: int, relative_path: str) -> Path:
    workspace_root = _user_workspace(user_id)
    cleaned = relative_path.strip()
    if not cleaned or cleaned == ".":
        return workspace_root
    target = (workspace_root / cleaned).resolve()
    if not str(target).startswith(str(workspace_root)):
        raise ValueError(f"Path escapes workspace boundary: {relative_path!r}")
    return target


def _build_exec_script(code: str, workspace_dir: str) -> str:
    return f"""import os, sys, io, json

os.environ["MPLBACKEND"] = "Agg"
import matplotlib
matplotlib.use("Agg")

os.chdir({json.dumps(workspace_dir)})
sys.path.insert(0, {json.dumps(workspace_dir)})

{code}
"""


# ═══════════════════════════════════════════════════════════════════════
# Capability: data-analysis:run
# ═══════════════════════════════════════════════════════════════════════
async def _run(params: dict, caller: str) -> dict:
    user_id = _resolve_user_id(caller)
    workspace = _user_workspace(user_id)
    workspace_real = str(workspace.resolve())
    code = params.get("code", "").strip()
    timeout = int(params.get("timeout", _DEFAULT_TIMEOUT))
    input_file_ids = params.get("input_files", []) or []

    if not code:
        return {"success": False, "error": "No code provided"}

    if timeout <= 0 or timeout > _MAX_TIMEOUT:
        timeout = _DEFAULT_TIMEOUT

    imported_files = []
    if input_file_ids:
        for fid in input_file_ids:
            file_id = int(fid)
            async with AsyncSessionLocal() as db:
                from app.services.file_service import check_file_access
                from app.services.file_preview_service import _resolve_storage_path
                try:
                    file_record = await check_file_access(db, file_id, user_id)
                except (NotFound, AppException) as exc:
                    return {"success": False, "error": f"Input file {file_id} access denied: {exc}"}
                src_path = _resolve_storage_path(file_record)
                if not src_path or not src_path.exists():
                    return {"success": False, "error": f"Input file {file_id} not found on disk"}
                target_name = f"{file_record.name}.{file_record.extension}" if file_record.extension else file_record.name
                target = workspace / target_name
                shutil.copy2(str(src_path), str(target))
                imported_files.append(target_name)

    run_id = uuid.uuid4().hex[:12]
    run_dir = workspace / f".da_{run_id}"
    run_dir.mkdir(parents=True, exist_ok=True)

    script_content = _build_exec_script(code, str(run_dir))
    script_path = run_dir / "script.py"
    script_path.write_text(script_content, encoding="utf-8")

    safe_env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": workspace_real,
        "WORKSPACE": workspace_real,
        "LANG": os.environ.get("LANG", "en_US.UTF-8"),
        "LC_ALL": os.environ.get("LC_ALL", "en_US.UTF-8"),
        "MPLBACKEND": "Agg",
        "PYTHONDONTWRITEBYTECODE": "1",
    }

    logger.info("user=%s data-analysis:run (timeout=%ss, input_files=%s)", user_id, timeout, input_file_ids)

    try:
        proc = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=str(run_dir),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=safe_env,
        )
    except subprocess.TimeoutExpired:
        shutil.rmtree(str(run_dir), ignore_errors=True)
        return {"success": False, "error": f"Execution timed out after {timeout}s", "timed_out": True, "stdout": "", "stderr": f"Timeout after {timeout}s"}
    except Exception as exc:
        shutil.rmtree(str(run_dir), ignore_errors=True)
        return {"success": False, "error": f"Execution failed: {exc}", "stdout": "", "stderr": str(exc)}

    charts = []
    for fpath in run_dir.iterdir():
        if fpath.is_file() and fpath.suffix.lower() in _CHART_EXTENSIONS:
            try:
                file_bytes = fpath.read_bytes()
                async with AsyncSessionLocal() as db:
                    from app.services import file_upload_service
                    result = await file_upload_service.upload_file(
                        db, io.BytesIO(file_bytes), fpath.name, user_id, None,
                    )
                    charts.append({
                        "file_id": result["id"],
                        "name": result["name"],
                        "size": result["size"],
                        "deduplicated": result.get("deduplicated", False),
                    })
            except Exception as exc:
                logger.warning("user=%s failed to upload chart %s: %s", user_id, fpath.name, exc)

    stdout = proc.stdout or ""
    stderr = proc.stderr or ""
    stdout_truncated = len(stdout) > _MAX_OUTPUT_BYTES
    stderr_truncated = len(stderr) > _MAX_OUTPUT_BYTES
    if stdout_truncated:
        stdout = stdout[:_MAX_OUTPUT_BYTES] + "\n... [stdout truncated at 1MB]"
    if stderr_truncated:
        stderr = stderr[:_MAX_OUTPUT_BYTES] + "\n... [stderr truncated at 1MB]"

    shutil.rmtree(str(run_dir), ignore_errors=True)

    return {
        "success": proc.returncode == 0,
        "return_code": proc.returncode,
        "stdout": stdout,
        "stderr": stderr,
        "stdout_truncated": stdout_truncated,
        "stderr_truncated": stderr_truncated,
        "charts": charts,
        "chart_count": len(charts),
    }


# ═══════════════════════════════════════════════════════════════════════
# Capability: data-analysis:chart — simplified "foolproof" charting
# ═══════════════════════════════════════════════════════════════════════
async def _chart(params: dict, caller: str) -> dict:
    user_id = _resolve_user_id(caller)
    data = params.get("data", [])
    chart_type = params.get("chart_type", "line")
    title = params.get("title", "")
    x_label = params.get("x_label", "")
    y_label = params.get("y_label", "")

    if not data:
        return {"success": False, "error": "No data provided"}
    if chart_type not in ("line", "bar", "pie"):
        return {"success": False, "error": f"Unsupported chart type: {chart_type}"}

    script_lines = [
        "import matplotlib",
        'matplotlib.use("Agg")',
        "import matplotlib.pyplot as plt",
        "import json",
        "",
        f"data = {json.dumps(data)}",
        f"title = {json.dumps(title)}",
        f"x_label = {json.dumps(x_label)}",
        f"y_label = {json.dumps(y_label)}",
        "",
    ]

    if chart_type == "pie":
        script_lines.extend([
            "labels = [str(d.get('x', d.get('label', ''))) for d in data]",
            "values = [float(d.get('y', d.get('value', 0))) for d in data]",
            "fig, ax = plt.subplots(figsize=(10, 8))",
            "ax.pie(values, labels=labels, autopct='%1.1f%%', startangle=90)",
            "ax.axis('equal')",
        ])
    elif chart_type in ("line", "bar"):
        script_lines.extend([
            "xs = [str(d.get('x', '')) for d in data]",
            "ys = [float(d.get('y', 0)) for d in data]",
            "fig, ax = plt.subplots(figsize=(12, 6))",
        ])
        if chart_type == "line":
            script_lines.extend([
                "ax.plot(xs, ys, marker='o', linewidth=2, markersize=6)",
                "ax.grid(True, linestyle='--', alpha=0.6)",
            ])
        else:
            script_lines.extend([
                "ax.bar(xs, ys, color='#2395bc', edgecolor='white', linewidth=0.5)",
            ])

    script_lines.extend([
        "if title:",
        "    ax.set_title(title, fontsize=14, pad=15)",
        "if x_label:",
        "    ax.set_xlabel(x_label)",
        "if y_label:",
        "    ax.set_ylabel(y_label)",
        "",
        "plt.xticks(rotation=45, ha='right')",
        "plt.tight_layout()",
        'plt.savefig("chart.png", dpi=150)',
        'print(f"Chart saved: chart.png")',
    ])

    script = "\n".join(script_lines)
    exec_params = {"code": script, "timeout": 30}
    return await _run(exec_params, caller)


# ═══════════════════════════════════════════════════════════════════════
# Register capabilities
# ═══════════════════════════════════════════════════════════════════════

register_capability(
    "data-analysis",
    "run",
    _run,
    description=(
        "在受限 Python 子进程中执行数据分析代码。预置 pandas/numpy/matplotlib（Agg 后端）。"
        "代码用 plt.savefig() 存图、print() 输出文本。自动收集生成的图表文件并存入框架文件系统。"
        "input_files 传入 file_id 列表，框架自动备到工作区供代码读取。"
        "超时、输出截断 1MB、工作区隔离。适用数据分析/算账/出图场景。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "code": {"type": "string", "description": "要执行的 Python 代码。可用 pandas/numpy/matplotlib（Agg 后端）。用 plt.savefig() 出图、print() 输出文本。"},
            "input_files": {"type": "array", "items": {"type": "integer"}, "description": "输入文件 file_id 列表（可选），备到工作区供代码读取"},
            "timeout": {"type": "integer", "description": "超时秒数（默认 60s，最大 600s）", "default": 60},
        },
        "required": ["code"],
    },
    min_role="editor",
)

register_capability(
    "data-analysis",
    "chart",
    _chart,
    description="傻瓜式出图。传入数据数组和图表类型，后端用 matplotlib 直接出图存文件。支持折线(line)/柱状(bar)/饼图(pie)。",
    parameters={
        "type": "object",
        "properties": {
            "data": {"type": "array", "description": "数据数组，每个元素含 x/y 字段：[{x:'一月', y:100}, ...]"},
            "chart_type": {"type": "string", "enum": ["line", "bar", "pie"], "description": "line(折线)/bar(柱状)/pie(饼图)"},
            "title": {"type": "string", "description": "图表标题（可选）"},
            "x_label": {"type": "string", "description": "X 轴标签（可选）"},
            "y_label": {"type": "string", "description": "Y 轴标签（可选）"},
        },
        "required": ["data", "chart_type"],
    },
    min_role="editor",
)


# ═══════════════════════════════════════════════════════════════════════
# HTTP endpoints — for direct testing / sandbox debugging
# ═══════════════════════════════════════════════════════════════════════

class RunRequest(BaseModel):
    code: str
    input_files: list[int] = []
    timeout: int = _DEFAULT_TIMEOUT


class ChartDataPoint(BaseModel):
    x: str | float = ""
    y: float = 0


class ChartRequest(BaseModel):
    data: list[ChartDataPoint]
    chart_type: str = "line"
    title: str = ""
    x_label: str = ""
    y_label: str = ""


@router.get("/health")
async def health():
    return ApiResponse(data={"module": "data-analysis", "status": "ok"})


@router.post("/run")
async def http_run(
    body: RunRequest,
    user: User = Depends(require_permission("editor")),
):
    result = await _run(body.model_dump(), f"user:{user.id}")
    return ApiResponse(data=result)


@router.post("/chart")
async def http_chart(
    body: ChartRequest,
    user: User = Depends(require_permission("editor")),
):
    result = await _chart(body.model_dump(), f"user:{user.id}")
    return ApiResponse(data=result)
