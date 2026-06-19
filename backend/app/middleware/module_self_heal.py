"""Module Self-Heal Middleware (模块按需自愈).

当请求命中加载失败的模块时，框架当场重试 import 该模块 router:
  - 成功 → 动态挂载路由 + 清掉 module_errors + 日志记录
  - 失败 → 返回 503 + 明确的模块级错误（含模块名、错误原文、日志路径）
  - 节流：同一模块重试最小间隔 5s，避免每个失败请求都重 import 打爆

所有健康模块的路由不受影响——正常请求旁路本中间件。
"""

import logging
import time

from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.routers.registry import (
    clear_module_error,
    extract_module_key_from_path,
    get_module_load_errors,
    try_retry_module_router,
)

logger = logging.getLogger("v2.module_self_heal")

RETRY_INTERVAL = 5.0  # seconds


class ModuleSelfHealMiddleware(BaseHTTPMiddleware):
    """Middleware that intercepts requests to failed modules and attempts self-heal."""

    def __init__(self, app, fastapi_app=None):
        super().__init__(app)
        # fastapi_app must be explicitly passed — in Starlette's middleware stack,
        # ``app`` is the NEXT middleware, not the FastAPI instance.
        self._fastapi_app = fastapi_app
        self._retry_timestamps: dict[str, float] = {}  # module_key -> last attempt time

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # 1. Check if this path belongs to a known module
        module_key = extract_module_key_from_path(path)
        if not module_key:
            # Not a module endpoint — pass through
            return await call_next(request)

        # 2. Check if this module has load errors
        errors = get_module_load_errors()
        if module_key not in errors:
            # Module loaded fine — pass through
            return await call_next(request)

        # 3. Module is broken — try self-heal with throttling
        now = time.time()
        last_retry = self._retry_timestamps.get(module_key, 0.0)

        if now - last_retry < RETRY_INTERVAL:
            # Throttled — return 503 with cached error
            logger.warning(
                "Module '%s' self-heal throttled (last=%ds ago, min=%ds)",
                module_key, int(now - last_retry), int(RETRY_INTERVAL),
            )
            return JSONResponse(
                status_code=503,
                content={
                    "success": False,
                    "data": None,
                    "error": f"Module '{module_key}' is broken: {errors[module_key]}",
                    "hint": f"see logs/modules/{module_key}.log",
                },
            )

        # 4. Attempt self-heal
        self._retry_timestamps[module_key] = now
        router, error = try_retry_module_router(module_key)
        if router:
            # Success — dynamically mount the router and clear error
            self._fastapi_app.include_router(router)
            clear_module_error(module_key)
            logger.info(
                "Module '%s' self-healed and restored dynamically", module_key,
            )
            # Now the module's routes should be available — proceed with the request
            return await call_next(request)
        else:
            # Still broken — return 503
            logger.warning(
                "Module '%s' self-heal failed: %s", module_key, error,
            )
            return JSONResponse(
                status_code=503,
                content={
                    "success": False,
                    "data": None,
                    "error": f"Module '{module_key}' is broken: {error}",
                    "hint": f"see logs/modules/{module_key}.log",
                },
            )
