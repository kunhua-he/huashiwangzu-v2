---
agent: opencode
task: ClaudeCode深化落地收口-技能激活-hook跨worker-预算死代码
date: 2026-06-24
---

## 变更记录

1. **技能系统可观测性** — engine.py 增加 4 处日志，技能发现/注入在日志中可见
2. **Hook 生命周期跨 worker 持久化** — 删除 `_HOOK_LIFECYCLE_STATE` 模块级 dict，新增 `agent_maintenance_state` 表 + `AgentMaintenanceState` 模型，`get_hook_lifecycle_state()` 读取 DB 作为真相源
3. **预算死代码清理** — 删除 `DiminishingBudgetTracker._rounds` 未使用字段

## 关联文件

- `modules/agent/backend/engine/engine.py` — 技能日志
- `modules/agent/backend/engine/post_turn_hooks.py` — hook 生命周期 DB 持久化
- `modules/agent/backend/engine/budget_allocator.py` — 死代码清理
- `modules/agent/backend/init_db.py` — 表迁移
- `modules/agent/backend/models.py` — AgentMaintenanceState 模型

## 遗留

- 对话端点 `MissingGreenlet` 错误为预存 bug，非本任务引入
- 背景维护 300s 后才首次触发，`run_count` 跨 worker 可能低估

## 2026-06-24 小马仔复核补充

- 审计 `ClaudeCode融合方案-控制面收口与补丁清理-大信` 回执后，确认入口拆分方向基本可信：`bootstrap.py` / `schemas.py` / `_utils.py` 已承担 router 原有部分职责。
- 发现回执中“边界收紧”仍有尾巴：`modules/agent/backend/router.py` 的 `/profiles` 仍直接 import `app.gateway.router.gateway_router`。
- 已补小修：在 `backend/app/gateway/router.py` 增加纯函数 `list_model_profiles()`，框架 gateway router 与 agent router 共用该函数，避免 agent `/profiles` 直接摸 `gateway_router` 实例。
- 已补小修：`modules/agent/backend/engine/layered_memory.py` 的 `record_recall_quality()` 后台写入增加 done callback 和 thread fallback 异常诊断，失败进入 `failure_diagnostics` 或日志，不再静默丢失。
- 验证：`python3.14 -m py_compile backend/app/gateway/router.py modules/agent/backend/router.py modules/agent/backend/engine/layered_memory.py` 通过；`cd backend && .venv/bin/python -m pytest tests/test_agent_regression.py tests/test_agent_e2e_regression.py` 100 passed，1 个 pytest fixture deprecation warning。
