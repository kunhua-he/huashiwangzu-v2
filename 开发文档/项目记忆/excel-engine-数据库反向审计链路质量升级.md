---
name: "excel-engine 数据库反向审计链路质量升级"
type: "task"
tags: [excel-engine, audit, db-reverse, verification]
agent: "codex-excel-engine-worker-20260703-r1"
created: "2026-07-03T06:23:30.041830+00:00"
---

# 改了什么
- 只改 `modules/excel-engine/**`：收口 create/import/update/append/undo/redo/history/version/compile 链路。
- 修复 snapshot 浅引用污染，写操作成功后才记录操作前快照并清 redo。
- 新增完整状态持久化，统一写入 cells/styles/merges/col_widths/row_heights/sheet 尺寸。
- 修复 append_rows 从 B 列开始的偏移；create_workbook 的 name 现在落库。
- 实现 table shift 四个空操作，去掉 code:0 假成功。
- 补 `export.save_version` 版本落库，restore_version 恢复完整状态；compile_xlsx 缺失 workbook 返回结构化失败。
- README 记录 2026-07-03 反向审计结论和验收命令。

# 验证了什么
- ruff: `modules/excel-engine/backend/router.py`, `state/db_ops.py`, `state/manager.py`, `table/row_col.py`, `sandbox/test_module.py` 全过。
- `cd modules/excel-engine/sandbox && ../../../backend/.venv/bin/python test_module.py` 全过，覆盖真实 XLSX 宽高导入、update/append、undo/redo、history、save/list/restore version、compile_xlsx，并清理测试数据。
- `cd frontend && npm run build` 通过。
- 活系统重启后 `/api/health` ok；`call_capability` create/update/append/undo/redo/list_history/compile 成功链路通过；缺失 workbook 的 compile 返回 `success:false`。
- 测试 state_key 和 compile 临时文件已清理，SQL 复核为空。

# 残留风险
- 当前整个工作区有许多其他 agent 的非 excel-engine 改动，`finish_task` 全局边界因此标红；本任务自身改动用 `git diff --name-only -- modules/excel-engine` 确认为 7 个 excel-engine 文件。
- db_reverse_audit 在清理测试数据后仍显示 `excel_col_widths/excel_row_heights/excel_redo_stack/excel_versions` 为空；这代表当前生产数据没有保留这些流程样本，不代表链路不可用，sandbox 已证明执行中会写入并清理。

# 关联 commit
- 未提交。
