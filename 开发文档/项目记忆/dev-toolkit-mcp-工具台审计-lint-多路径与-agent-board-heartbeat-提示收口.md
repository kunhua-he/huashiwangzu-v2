---
name: "dev_toolkit MCP 工具台审计：lint 多路径与 agent_board heartbeat 提示收口"
type: "task"
tags: [dev-toolkit, mcp, audit, agent-board, lint]
agent: "codex-devtool-audit-worker-20260703-r1"
created: "2026-07-03T06:06:19.932520+00:00"
---

# 改了什么

- 审计 dev_toolkit 工具台质量，重点看假绿/流程摩擦、队列与 agent_board 落盘、finish_task/memory_write/mcp_feedback 流程。
- `dev_toolkit/code_tools.py`：`lint(path, diff)` 从单路径改为支持逗号/换行分隔多路径；单路径保持原返回形状，多路径返回汇总、逐文件结果和 failed_count，避免文档/finish_task 说支持多文件但直接调用 lint 时假失败。
- `dev_toolkit/agent_board_tools.py`：`agent_board_heartbeat` 对未 claim 的任务仍 fail closed，但返回 `hint` 和 `claim_example`，明确必须先 `agent_board_claim`，避免节点心跳因 task not found 后无恢复路径。
- `dev_toolkit/README.md`：同步 lint 多路径和 agent_board 先 claim 再 heartbeat 的事实。
- 新增/更新测试：`test_lint_accepts_comma_and_newline_separated_paths`、`test_agent_board_heartbeat_missing_task_points_to_claim`。

# 验证了什么

- `backend/.venv/bin/python -m pytest dev_toolkit/test_agent_board_tools.py dev_toolkit/test_server_helpers.py -q`：42 passed。
- `backend/.venv/bin/python -m pytest dev_toolkit/test_mcp_entry.py dev_toolkit/test_insight_tools.py -q`：5 passed。
- `finish_task` 复跑合并目标：47 passed。
- `backend/.venv/bin/ruff check dev_toolkit/code_tools.py dev_toolkit/agent_board_tools.py dev_toolkit/test_server_helpers.py dev_toolkit/test_agent_board_tools.py`：All checks passed。
- 新 Python 进程直接导入磁盘版 `dev_toolkit.code_tools`，验证 lint 多路径返回 2 条真实结果、CALL_COUNT=2。
- `mcp_self_check`：74 tools，无 duplicate/orphan；server.py 仍超过 600 行是既有警告。

# 是否还有残留风险

- 共享工作区已有其他 agent 的 backend/app、backend/tests、modules 改动；本轮没有修改这些文件，也不回滚。
- `finish_task` 仍缺 allowed_prefixes 参数；因此全局但限目录的任务需要额外手动跑 `worktree_guard(allowed_prefixes=...)` 区分他人改动。

# 关联 commit

- 未提交。
