---
name: "W3 excel-engine state_key owner isolation and version IDOR fix"
type: "task"
tags: [excel-engine, state_key, IDOR, 版本权限, pytest]
agent: "W3-codex"
created: "2026-07-02T11:45:09.034724+00:00"
---

# 改了什么
- 在 `modules/excel-engine/backend/models.py` 将 `excel_workbooks.state_key` 从全局唯一改为 `(owner_id, state_key)` 复合唯一；新增 `modules/excel-engine/backend/init_db.py` 启动期幂等迁移，删除旧 `excel_workbooks_state_key_key` 约束并创建 `ux_excel_wb_owner_state_key`。
- `state/db_ops.py` 的 `find_workbook/find_or_create/read_history/read_state/archive` 全部支持 owner 过滤，自动版本写入记录 `creator_id`，sheet 写入前加 `SELECT ... FOR UPDATE` 行锁。
- `router.py` 增加 `knowledge_{file_id}` 解析与 `check_file_access` 校验；普通 state_key 走当前 user，knowledge state 读走文件 owner，写操作保守 owner-only；版本 list/restore 均按 `file_id + creator_id/owner` 过滤，拒绝裸 `version_id` 跨文件恢复。
- sandbox 测试增加真实数据库覆盖：同 state_key 不同 owner 隔离、跨文件 version_id restore 越权失败，并清理测试数据。

# 验证了什么
- `backend/.venv/bin/ruff check modules/excel-engine/backend/models.py modules/excel-engine/backend/init_db.py modules/excel-engine/backend/state/db_ops.py modules/excel-engine/backend/router.py modules/excel-engine/sandbox/test_module.py` 通过。
- `backend/.venv/bin/python -m py_compile ...` 通过。
- `backend/.venv/bin/python modules/excel-engine/sandbox/test_module.py` 通过。
- `cd backend && .venv/bin/python -m pytest ../modules/excel-engine/sandbox/test_module.py -q`：11 passed，只有既有 `datetime.utcnow()` DeprecationWarning。
- 测试后查询 `w3_excel_file_%` 和 `w3_state_isolation_%` 残留均为 0。

# 是否还有残留风险
- 共享文件 edit 权限未放开写入；当前按 owner-only 处理，因为可复用的框架写 helper `replace_file_content` 也是 owner-only。若后续框架提供正式 shared-edit 写 helper，可替换 `_resolve_state_owner_id(write=True)` 的判断。
- 收工 `finish_task` 因工作区有其他会话既有 dirty 文件报告边界失败；本任务实际修改仅在 `modules/excel-engine/` 范围。

# 关联 commit
- 未提交。
