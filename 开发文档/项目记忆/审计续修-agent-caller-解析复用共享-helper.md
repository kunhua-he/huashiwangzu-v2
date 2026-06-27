---
name: "审计续修：agent caller 解析复用共享 helper"
type: task
tags: ["审计", "caller", "agent", "access-control"]
created: 2026-06-27
agent: codex
---

# 改了什么

- `modules/agent/backend/handlers/tool.py` 删除本地 `_resolve_user_id`，改为复用 `app.services.file_reader.resolve_caller_user_id`。
- 覆盖 agent profile/signal/trajectory 相关能力里的 owner_id 解析调用，行为与原实现一致：只接受 `user:{id}`，非法 caller 抛 `PermissionDenied`。

# 验证了什么

- `cd backend && .venv/bin/ruff check ../modules/agent/backend/handlers/tool.py` 通过。
- `python3 scripts/check-capability-drift.py` 通过，106 registered public capabilities。

# 是否还有残留风险

- `modules/im/backend/router.py` 和 `modules/memory/backend/services/memory_service.py` 仍保留本地 `_parse_user_id`，因为当前语义是非法 caller 返回 0，不等价于共享 helper 的拒绝；memory 还有测试直接检查该函数存在。后续若要统一，需要先明确非法 caller 的权限语义并调整测试。

# 关联 commit

- 未提交。
