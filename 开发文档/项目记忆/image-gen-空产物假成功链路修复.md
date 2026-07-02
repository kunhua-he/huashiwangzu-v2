---
name: "image-gen 空产物假成功链路修复"
type: "task"
tags: [fake-success, audit, image-gen, task-worker]
agent: "fake-success-audit-worker"
created: "2026-07-02T16:01:32.651102+00:00"
---

# 改了什么
- 修复 `modules/image-gen/backend/router.py`：provider 返回空结果或 URL 下载全部失败时，不再保存/返回 `success + images: []`，而是写入 `imagegen_records.status=failed` 并抛 `ValidationError`。
- 修复 `image-gen:usage_history` 查询异常返回空列表的假空流，改为抛 `AppException` 进入统一失败响应。
- 在 `backend/tests/test_empty_flow_audit_regressions.py` 补回归断言，防止空图片/空历史假成功回退。

# 验证了什么
- `cd backend && .venv/bin/python -m pytest tests/test_empty_flow_audit_regressions.py tests/test_event_bus_retry.py tests/test_agent_scheduler_task_semantics.py tests/test_task_worker_semantics.py`：20 passed。
- `cd backend && .venv/bin/ruff check app/services/event_bus.py tests/test_empty_flow_audit_regressions.py tests/test_event_bus_retry.py tests/test_agent_scheduler_task_semantics.py tests/test_task_worker_semantics.py ../modules/scheduler/backend/router.py ../modules/agent/backend/handlers/tasks.py ../modules/agent/backend/runtime/task_sink.py ../modules/image-gen/backend/router.py`：All checks passed。
- 项目工具台 `probe GET /api/health`：success true / status ok / worker running / semantic_failed_completed_24h=0。

# 是否还有残留风险
- 当前工作区有大量并行脏改动，未回退也未覆盖；本次只归因 `modules/image-gen/backend/router.py` 与 `backend/tests/test_empty_flow_audit_regressions.py` 的补丁。
- `/api/health` 仍显示历史 task_queue failed 899，是既有债务，不是本次新增。

# 关联 commit
- 未提交。
