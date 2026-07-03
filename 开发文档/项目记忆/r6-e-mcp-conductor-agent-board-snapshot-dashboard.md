---
name: "R6-E MCP conductor agent board snapshot dashboard"
type: "task"
tags: [r6, mcp, dev-toolkit, conductor, agent-board]
agent: "codex-r6-mcp-conductor-e"
created: "2026-07-03T16:06:36.562929+00:00"
---

# 改了什么

- 增强 `agent_board_snapshot`：默认返回 `conductor` 区块，聚合 lanes、stale_tasks、recent_memory_links、stage_plan。
- 新增 `dev_toolkit/agent_board_conductor.py` 承载多代理控制台汇总逻辑，避免 `agent_board_tools.py` 超过 600 行。
- `stage_plan` 会按顶层路径生成 `grouped_pathspecs` 和可直接使用的 `git add -- ...` 命令，方便主会话给 5 线程切片提交。
- 测试覆盖 stale claimed task、completed result_summary、最近项目记忆链接、dirty file 分组 pathspec，以及 tool schema 暴露 include_conductor/stale_after_seconds/memory_limit。

# 验证了什么

- `ruff check` 通过：`dev_toolkit/agent_board_tools.py`、`dev_toolkit/agent_board_conductor.py`、`dev_toolkit/test_agent_board_tools.py`。
- `pytest dev_toolkit/test_agent_board_tools.py`：8 passed。
- `/api/health` 返回 status ok，backend tail_log 为空。
- 新 Python 进程调用 `snapshot(..., repo_root=repo)` 返回 conductor keys：lanes/recent_memory_links/stage_plan/stale_after_seconds/stale_tasks，并输出 grouped `git add -- ...` 样例。

# 是否还有残留风险

当前 Codex 会话里的 MCP stdio server 已在改动前加载模块，可能要等工具台 MCP 重启/重载后，`agent_board_snapshot` 的工具元数据和默认输出才会在本会话直接显示新字段。实现本身已由单测和新进程验证。工作区还有 frontend/tests、modules/knowledge、modules/media-intelligence 的并行 worker 改动，我没有触碰。

# 关联 commit

未提交。
