---
name: "审计续修：模型网关统一重试迁移到 tenacity"
type: task
tags: ["审计", "网关", "retry", "tenacity"]
created: 2026-06-27
agent: codex
---

# 改了什么

- 将 `backend/app/gateway/router.py` 的 `_call_with_unified_retry` 从手写 `for + asyncio.sleep` 循环迁移到 `tenacity.AsyncRetrying`。
- 保留现有 `classify_error` / `compute_delay` 分类和退避策略，tenacity 只负责调度重试。
- 用 `_RetryableGatewayError` 包装可重试异常，确保最终仍返回项目统一的 `ModelResponse`，不向上泄露第三方异常。
- `backend/requirements.txt` 显式增加 `tenacity>=9.0.0`，避免依赖虚拟环境里偶然已安装。

# 验证了什么

- `cd backend && .venv/bin/python -m pytest tests/test_gateway_retry.py` 2 passed。
- `cd backend && .venv/bin/python -m pytest tests/test_gateway_adapters.py tests/test_gateway_retry.py tests/test_opencode_provider.py` 27 passed。
- `cd backend && .venv/bin/ruff check app/gateway/router.py tests/test_gateway_retry.py` 通过。
- `python3 scripts/check-capability-drift.py` 通过，106 registered public capabilities。

# 是否还有残留风险

- 网关重试行为仍依赖现有错误分类器，未改变 `rate_limit/server/timeout/auth/quota` 分类语义。
- Vision/image generation 里仍有各自 fallback/retry 逻辑，未在本轮合并，后续可继续收口。

# 关联 commit

- 未提交。
