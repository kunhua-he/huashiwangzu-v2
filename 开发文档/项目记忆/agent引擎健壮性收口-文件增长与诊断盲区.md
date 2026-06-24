# Agent 引擎健壮性收口 — 第二轮：文件增长与诊断盲区

**Agent**: executor (opencode agent)
**日期**: 2026-06-24
**关联 Commit**: (未提交 — 本地 main 分支，用户确认后提交)

## 做了什么

三个问题一并收口：

### 1. hook_runs.json 二级增长控制
- `_HOOK_RUN_MAX_AGE_DAYS=7` — 写入时剪掉超 7 天记录
- `_HOOK_RUN_MAX_BYTES=1048576` (1MB) — 超限从头部剪掉最老 1/3
- `_trim_hook_runs()` 统一三约束 (age→count→bytes)，原子写路径不变

### 2. 静态记忆缓存 mtime 感知
- 缓存 value 增加 `file_mtimes: dict[str, float]`，命中时逐个文件校验 mtime
- 新增 `_check_cache_mtime()` — mtime 变了立即失效
- TTL 60s→300s 作为文件系统不支持 mtime 的兜底
- logger.debug 记录 HIT/mtime mismatch/TTL expired 三类日志
- recall_quality.json 同步增加 `_MAX_AGE_DAYS=30`、`_MAX_BYTES=2MB`、`_trim_recall_quality`

### 3. 异常诊断记录系统
- 新建 `failure_diagnostics.py` — JSONL 格式 + 512KB 上限 + append-only 原子写
- `record_failure(source, operation, error_type, error_message, conversation_id, extra)`
- 5 处埋点：hook._safe_run / hook._write_hook_runs_file / memory._write_recall_quality_file / chat._yield_final_stream / chat.event_stream
- 新端点 `GET /api/agent/admin/failure-diagnostics?limit=50`

## 验证

- 结构回归 82/82 passed
- E2E 回归 25/25 passed
- /api/agent/health → status:ok
- /api/agent/admin/failure-diagnostics → 正常返回
- /api/agent/admin/hook-lifecycle → 正常返回

## 涉及文件

```
M  modules/agent/backend/engine/post_turn_hooks.py
M  modules/agent/backend/engine/layered_memory.py
A  modules/agent/backend/engine/failure_diagnostics.py
M  modules/agent/backend/handlers/admin.py
M  modules/agent/backend/handlers/chat.py
M  modules/agent/backend/router.py
M  backend/tests/test_agent_regression.py
M  backend/tests/test_agent_e2e_regression.py
```
