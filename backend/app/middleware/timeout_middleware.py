"""Request Timeout Middleware (请求超时 + SSE 豁免).

普通请求超过 30 秒自动断、返回 504，防止一个慢请求拖死整个 worker。
SSE / 流式端点（Agent 对话、Gateway 流式）豁免超时。

豁免端点：
  - /api/agent/chat          (SSE 流式对话)
  - /api/gateway/chat-stream  (Gateway 流式)
  - /api/gateway/chat         (非流式对话，但可能较慢)
"""

import asyncio
import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger("v2.timeout")

TIMEOUT_SECONDS = 60  # 60 seconds for regular requests

# 豁免超时的路径前缀（SSE/流式端点）
_SSE_EXEMPT_PREFIXES = (
    "/api/agent/chat",
    "/api/gateway/chat-stream",
)


def _is_sse_exempt(path: str) -> bool:
    """Check if a path should be exempt from the timeout."""
    for prefix in _SSE_EXEMPT_PREFIXES:
        if path.startswith(prefix):
            return True
    return False


class TimeoutMiddleware(BaseHTTPMiddleware):
    """Wrap request handling with asyncio.wait_for timeout."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        if _is_sse_exempt(path):
            # SSE endpoints — no timeout
            return await call_next(request)

        try:
            return await asyncio.wait_for(
                call_next(request),
                timeout=TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            logger.warning("Request timeout after %ds: %s %s", TIMEOUT_SECONDS, request.method, path)
            return JSONResponse(
                status_code=504,
                content={
                    "success": False,
                    "data": None,
                    "error": f"Request timed out after {TIMEOUT_SECONDS}s",
                    "hint": "The operation took too long. If this is a long-running task, "
                            "check server logs or break it into smaller steps.",
                },
            )
