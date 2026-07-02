---
name: "项目工具台 db_reverse_audit 数据库反向审计工具"
type: "task"
tags: [dev-toolkit, mcp, db-audit, read-only]
agent: "codex-devtool-db-reverse-worker"
created: "2026-07-02T15:30:11.019663+00:00"
---

# 改了什么

- 新增 `dev_toolkit/db_reverse_tools.py`，提供 `db_reverse_audit`：从 public 表反推 likely_owner/module、router/manifest/capability/code 引用，输出 empty/non-empty 和 expected_empty/suspicious_empty/requires_flow_probe 分级。
- 接入 `dev_toolkit/server.py` 的组件化 tools/list 与 call_tool 分发；更新 `dev_toolkit/README.md` 工具清单。
- 新增 `dev_toolkit/test_db_reverse_tools.py`，用 fake SQL/monkeypatch 覆盖空表分级、filter/countless 模式、写 SQL 启动 psql 前拒绝。
- 顺手修复 `dev_toolkit/code_tools.py` 的 `run_test`：dev_toolkit/模块等 repo-root 绝对测试目标改用仓库根 cwd 并注入 `PYTHONPATH`，避免工具台自身测试在 backend cwd 下 import 失败；`test_server_helpers.py` 补回归。

# 验证了什么

python3.14 -m pytest dev_toolkit/test_db_reverse_tools.py dev_toolkit/test_insight_tools.py dev_toolkit/test_server_helpers.py -> 38 passed; backend/.venv/bin/ruff check dev_toolkit/db_reverse_tools.py dev_toolkit/test_db_reverse_tools.py dev_toolkit/code_tools.py dev_toolkit/test_server_helpers.py dev_toolkit/server.py -> All checks passed; MCP run_test same target -> success true / 38 passed; MCP db_reverse_audit real DB framework_file_shares -> expected_empty.

# 是否还有残留风险

- 工作区有大量其他 agent 既有未提交改动，本任务未 revert。
- owner 与 expected-empty 规则是启发式，后续可根据真实审计反馈继续扩充别名和表类别。

# 关联 commit

未提交。
