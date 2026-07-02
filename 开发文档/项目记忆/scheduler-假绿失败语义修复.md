---
name: "Scheduler 假绿失败语义修复"
type: "task"
tags: [scheduler, false-green, task-worker, 20260702]
agent: "codex-scheduler-false-green-worker"
created: "2026-07-02T14:42:36.029208+00:00"
---

# 改了什么
- `modules/scheduler/backend/router.py`：`scheduler:list` 能力在 caller 无法解析或解析为空时返回 `success:false`，不再伪装成成功空列表。
- `modules/scheduler/backend/router.py`：新增 Agent capability 结果语义判定，`success:false`、顶层/内层 `status=failed/error`、`error` 字段或异常都会让 `scheduled_agent_job` 返回 `success:false,status:failed`。
- `backend/tests/test_agent_scheduler_task_semantics.py`：补 invalid caller、空 user id、Agent 返回失败语义、Agent 抛异常的 focused tests；保留正常成功路径测试。

# 验证了什么
- Ruff：`modules/scheduler/backend/router.py` 通过。
- Ruff：`backend/tests/test_agent_scheduler_task_semantics.py` 通过。
- Pytest：`cd backend && .venv/bin/python -m pytest tests/test_agent_scheduler_task_semantics.py`，9 passed。
- Sandbox：`backend/.venv/bin/python -m pytest modules/scheduler/sandbox/test_module.py`，11 passed。
- 活栈：`/api/health` 200，status ok，worker 已注册 `scheduled_agent_job`。

# 残留风险
- 当前工作区有其他会话的 dev_toolkit、agent、knowledge、content、event_bus dirty 文件；本节点实际 diff 只在 scheduler router 和 scheduler 语义测试。

# 关联 commit
- 未提交，等待主会话统一集成。
