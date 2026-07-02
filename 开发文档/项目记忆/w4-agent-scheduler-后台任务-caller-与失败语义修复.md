---
name: "W4 Agent Scheduler 后台任务 caller 与失败语义修复"
type: "task"
tags: [agent, scheduler, task-worker, background-task, caller-semantics]
agent: "codex-w4"
created: "2026-07-02T11:36:25.523929+00:00"
---

## 做了什么
- 修复 scheduler 后台执行 Agent/IM 时的 caller 语义：Agent 执行改用 `user:{creator_id}`，通知改用白名单 `system:task-worker`，不再使用未注册的 `scheduler:system` 或 `caller_role=admin` 假提升。
- 修复 Agent slow tool 后台失败语义：工具失败仍写入对话失败消息并发送失败通知，但 handler 返回 `success:false/status:failed`，让 task_worker 把队列任务按失败处理。
- 修复 subagent runner 的 `owner_id` 未定义问题：spawn_subagent 从 user caller 解析 owner_id，并传到 `skill_describe` 工具指引渲染路径。
- 将 memory distill 保存 memory 的 caller_role 从 admin 降为 viewer，匹配 `memory:save` 的实际 min_role。

## 验证
- ruff 通过：`modules/agent/backend/handlers/tasks.py`、`modules/agent/backend/handlers/tool.py`、`modules/agent/backend/services/subagent_runner.py`、`modules/scheduler/backend/router.py`、相关测试文件。
- pytest 通过：`backend/tests/test_task_worker_semantics.py backend/tests/test_agent_scheduler_task_semantics.py /Users/hekunhua/Documents/Agent/PHP/华世王镞_v2/modules/agent/backend/test_subagent_runner.py`，结果 6 passed。
- 残留扫描通过：目标路径未命中 `scheduler:system`、`system:agent_worker`、`caller_role="admin"`。

## 风险
- 当前工作区有大量其他会话 dirty/untracked 文件，本次只按 W4 范围修改 Agent/Scheduler 后台任务与相关测试；未运行全量 pytest。

## 关联 commit
- 未提交。
