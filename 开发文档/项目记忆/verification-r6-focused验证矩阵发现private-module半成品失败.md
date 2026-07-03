---
name: "verification-r6 focused验证矩阵发现private-module半成品失败"
type: "task"
tags: [verification-r6, focused-tests, private-modules, upload-sessions, parser-resource-diagnostics, dev-toolkit, 20260703]
agent: "verification-r6"
created: "2026-07-02T17:38:56.858600+00:00"
---

# verification-r6 节点记录

## 任务边界

本轮只做 focused 验证，不主动改代码。目标矩阵：task_queue_audit、file_upload_sessions、parser_resource_diagnostics、private_modules_lifecycle、dev_toolkit agent board/mcp entry、相关 ruff、git diff --check。

## 已验证通过

- `backend/tests/test_task_queue_audit.py`: 10 passed
- `backend/tests/test_file_upload_sessions.py`: 3 passed（有 FastAPI `on_event` 既有 warning）
- `backend/tests/test_parser_resource_diagnostics.py`: 7 passed
- `dev_toolkit/test_agent_board_tools.py`: 4 passed
- `dev_toolkit/test_mcp_entry.py`: 2 passed
- `git diff --check`: passed

## 失败与证据

1. `backend/tests/test_private_modules_lifecycle.py` 稳定失败：
   - 失败断言：deactivate 后访问 `/api/private/1/probe-private/ping`，预期 404，实际 200。
   - 只读定位：`backend/app/services/private_module_service.py` 的 `deactivate_private_module()` 中 `_unregister_private_module(owner_id, module_key, record.router_prefix)` 被缩进在 `if record.status != "active": return` 之后，属于不可达代码；因此 DB 状态可变 installed，但 runtime route 不会摘除。
   - 这是完整生命周期链路 bug，不是环境缺依赖。

2. ruff focused 失败：
   - `backend/tests/test_file_upload_sessions.py:3` I001 import block 未排序。
   - 其它本轮目标 Python 文件 ruff 均通过。

3. 工作区产物风险：
   - `backend/data/.upload_sessions/1/b8a3452f-74a8-487c-849c-83b8e887e9a0/00000000.part`
   - `backend/data/.upload_sessions/1/bbd365ba-9d0b-4347-9714-566cbaefd0ca/00000000.part`
   - 两个未跟踪分片文件均为 5 字节。需要确认是测试残留还是预期样本；按测试数据清理规则，不应直接带入提交。

## 工具台观察

`finish_task` 混合 backend/tests 和 dev_toolkit 测试目标时，把 backend 目标归一为仓库根下 `tests/...`，导致合跑假失败；本轮采用单项 `run_test` 与 shell pytest 结果作为权威证据。

## 结论

当前 diff 不适合作为稳定 checkpoint 推送主线：至少需要修 private module deactivate route unregister、整理 upload session 测试 import、处理 `.upload_sessions` 未跟踪残留，并重跑本矩阵。
