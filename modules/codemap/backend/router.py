"""FastAPI router for codemap module.

Provides 6 HTTP endpoints and 6 cross-module capabilities:
  codemap:get_file       — File-level code map info
  codemap:impact         — Transitive impact analysis
  codemap:check_boundary — Boundary compliance check
  codemap:module_map     — Module-level overview
  codemap:search         — Keyword search
  codemap:stats          — Index statistics

Index is built asynchronously on module import (not blocking startup).
Query returns "indexing" status while build is in progress.
"""

from __future__ import annotations

import logging
import threading

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.middleware.auth import require_permission
from app.models.user import User
from app.schemas.common import ApiResponse
from app.services.module_registry import register_capability

from .graph import get_graph
from .indexer import get_indexer
from .watcher import get_watcher

logger = logging.getLogger("v2.codemap.router")

router = APIRouter(prefix="/api/codemap", tags=["codemap"])

# ── Start background build on module import ──────────────────────────────────

_initialized = False
_init_lock = threading.Lock()


def _ensure_initialized() -> None:
    """Thread-safe one-shot initialisation: build index + start watcher."""
    global _initialized
    if _initialized:
        return
    with _init_lock:
        if _initialized:
            return
        logger.info("Starting codemap background index build...")
        indexer = get_indexer()
        indexer.build_async()

        try:
            watcher = get_watcher()
            watcher.start()
        except Exception as exc:
            logger.warning("File watcher failed to start: %s", exc)

        _initialized = True


_ensure_initialized()


# ── Request models ───────────────────────────────────────────────────────────

class GetFileRequest(BaseModel):
    path: str


class ImpactRequest(BaseModel):
    path: str
    symbol: str | None = None


class CheckBoundaryRequest(BaseModel):
    path: str | None = None
    module_key: str | None = None


class ModuleMapRequest(BaseModel):
    module_key: str


class SearchRequest(BaseModel):
    keyword: str


# ── Helper ───────────────────────────────────────────────────────────────────

def _check_ready() -> dict | None:
    """Return an error dict if the index is not ready, else None."""
    graph = get_graph()
    if not graph.ready:
        return {"success": False, "error": "索引构建中，请稍后重试", "data": {"status": "indexing"}}
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# HTTP Endpoints
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/health")
async def health():
    graph = get_graph()
    return ApiResponse(data={
        "module": "codemap",
        "status": "ok",
        "index_ready": graph.ready,
        "file_count": len(graph._files),
    })


@router.get("/stats")
async def http_stats(user: User = Depends(require_permission("viewer"))):
    graph = get_graph()
    return ApiResponse(data=graph.stats())


@router.post("/get-file")
async def http_get_file(
    body: GetFileRequest,
    user: User = Depends(require_permission("viewer")),
):
    not_ready = _check_ready()
    if not_ready:
        return ApiResponse(**not_ready)
    graph = get_graph()
    result = graph.get_file(body.path)
    if result is None:
        return ApiResponse(success=False, error=f"File not found: {body.path}", data=None)
    return ApiResponse(data=result)


@router.post("/impact")
async def http_impact(
    body: ImpactRequest,
    user: User = Depends(require_permission("viewer")),
):
    not_ready = _check_ready()
    if not_ready:
        return ApiResponse(**not_ready)
    graph = get_graph()
    result = graph.impact(body.path, body.symbol)
    return ApiResponse(data=result)


@router.post("/check-boundary")
async def http_check_boundary(
    body: CheckBoundaryRequest,
    user: User = Depends(require_permission("viewer")),
):
    not_ready = _check_ready()
    if not_ready:
        return ApiResponse(**not_ready)
    graph = get_graph()
    result = graph.check_boundary(path=body.path, module_key=body.module_key)
    return ApiResponse(data=result)


@router.post("/module-map")
async def http_module_map(
    body: ModuleMapRequest,
    user: User = Depends(require_permission("viewer")),
):
    not_ready = _check_ready()
    if not_ready:
        return ApiResponse(**not_ready)
    graph = get_graph()
    result = graph.module_map(body.module_key)
    return ApiResponse(data=result)


@router.post("/search")
async def http_search(
    body: SearchRequest,
    user: User = Depends(require_permission("viewer")),
):
    not_ready = _check_ready()
    if not_ready:
        return ApiResponse(**not_ready)
    graph = get_graph()
    result = graph.search(body.keyword)
    return ApiResponse(data=result)


# ═══════════════════════════════════════════════════════════════════════════════
# Cross-module capabilities (registered with framework registry)
# ═══════════════════════════════════════════════════════════════════════════════

async def _cap_get_file(params: dict, caller: str) -> dict:
    graph = get_graph()
    if not graph.ready:
        return {"success": False, "error": "索引构建中"}
    path = params.get("path", "")
    result = graph.get_file(path)
    if result is None:
        return {"success": False, "error": f"File not found: {path}"}
    return {"success": True, "data": result}


async def _cap_impact(params: dict, caller: str) -> dict:
    graph = get_graph()
    if not graph.ready:
        return {"success": False, "error": "索引构建中"}
    path = params.get("path", "")
    symbol = params.get("symbol")
    return {"success": True, "data": graph.impact(path, symbol)}


async def _cap_check_boundary(params: dict, caller: str) -> dict:
    graph = get_graph()
    if not graph.ready:
        return {"success": False, "error": "索引构建中"}
    path = params.get("path")
    module_key = params.get("module_key")
    return {"success": True, "data": graph.check_boundary(path=path, module_key=module_key)}


async def _cap_module_map(params: dict, caller: str) -> dict:
    graph = get_graph()
    if not graph.ready:
        return {"success": False, "error": "索引构建中"}
    module_key = params.get("module_key", "")
    return {"success": True, "data": graph.module_map(module_key)}


async def _cap_search(params: dict, caller: str) -> dict:
    graph = get_graph()
    if not graph.ready:
        return {"success": False, "error": "索引构建中"}
    keyword = params.get("keyword", "")
    return {"success": True, "data": graph.search(keyword)}


async def _cap_stats(params: dict, caller: str) -> dict:
    graph = get_graph()
    return {"success": True, "data": graph.stats()}


# Register all capabilities
register_capability(
    "codemap", "get_file", _cap_get_file,
    description="查询文件的代码地图信息：所属层/模块、语言、符号清单、依赖与被依赖、注册/调用的能力、涉及的表",
    parameters={
        "type": "object",
        "properties": {"path": {"type": "string", "description": "文件路径（相对项目根目录）"}},
        "required": ["path"],
    },
    min_role="viewer",
)

register_capability(
    "codemap", "impact", _cap_impact,
    description="查询影响面：正向+反向传递闭包，返回波及的文件、模块、跨模块能力清单和风险等级(high/medium/low)",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "文件路径"},
            "symbol": {"type": "string", "description": "符号名（可选，限定影响范围）"},
        },
        "required": ["path"],
    },
    min_role="viewer",
)

register_capability(
    "codemap", "check_boundary", _cap_check_boundary,
    description="检查文件或模块的边界合规性，返回违反铁律17-20的引用清单",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "文件路径"},
            "module_key": {"type": "string", "description": "模块 key（与 path 二选一）"},
        },
    },
    min_role="viewer",
)

register_capability(
    "codemap", "module_map", _cap_module_map,
    description="查询模块的对外能力、依赖的外部能力、边界健康状态",
    parameters={
        "type": "object",
        "properties": {"module_key": {"type": "string", "description": "模块 key"}},
        "required": ["module_key"],
    },
    min_role="viewer",
)

register_capability(
    "codemap", "search", _cap_search,
    description="按关键词模糊搜索文件和符号",
    parameters={
        "type": "object",
        "properties": {"keyword": {"type": "string", "description": "搜索关键词"}},
        "required": ["keyword"],
    },
    min_role="viewer",
)

register_capability(
    "codemap", "stats", _cap_stats,
    description="返回索引规模、构建耗时、最后更新时间、是否就绪",
    parameters={"type": "object", "properties": {}},
    min_role="viewer",
)
