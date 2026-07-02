---
name: "检查重启会话后的项目工具台 MCP 挂载与完整性"
type: "task"
tags: [mcp, dev-toolkit, session-health]
agent: "codex"
created: "2026-07-02T08:56:51.017590+00:00"
---

# 做了什么

检查 Codex 重启会话后的项目工具台 MCP 挂载状态。

# 结论

项目 MCP 已正确挂载，服务端 `dev_toolkit/server.py` 的 `list_tools()` 本地返回 43 个工具；`.mcp.json` 正确指向 `python3.14 dev_toolkit/server.py`。Codex 当前会话初始只暴露部分工具，但通过 `tool_search` 按需搜索后，`probe`、`tail_log`、`routes`、`capabilities`、`db_schema`、`code_explore`、`memory_recent`、`tool_usage_stats`、`sanity_check` 等关键工具均可加载并调用。

# 验证

- `brief`、`plan_task`、`worktree_guard` 调用成功。
- `probe(GET /api/health)` 返回 200，数据库 ok，module_errors 为 null，worker running。
- `routes('/api/health')`、`capabilities('agent')`、`db_schema()`、`code_explore(...)` 调用成功。
- `sanity_check` 返回 success=true，前端 5173 监听，后端健康，模块导入无错误。
- `tool_usage_stats` 能正常统计调用。

# 残留风险

不是 MCP 服务端不完整，而是 Codex 会话工具 schema 会延迟/按需暴露。重启后如果看不到某些项目工具，先用 `tool_search` 搜具体工具名或功能关键词。未运行 `smoke_all` / `release_gate`，因为本任务只检查 MCP 健康，不做重型回归。

# 关联 commit

无。
