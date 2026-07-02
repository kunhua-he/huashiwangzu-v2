---
name: "升级项目工具台MCP新增worktree_guard与tool_usage_stats"
type: task
tags: ["mcp", "dev-toolkit", "workflow", "guard", "usage-stats"]
created: 2026-07-02
agent: codex
---

2026-07-02 Codex 升级项目工具台 MCP：新增 worktree_guard 工具，用于开工/收工边界守卫，统计 dirty 文件并包含 untracked，按路径分组，支持 module_key、allowed_prefixes、forbidden_prefixes；finish_task 改为复用 worktree_guard，避免只用 git diff --name-only 漏掉未跟踪文件。新增 tool_usage_stats 工具，持久化统计每个 MCP 工具调用次数、成功/失败次数、平均耗时和最近调用时间，统计文件落在 backend/logs/tool_usage_stats.json（已被 gitignore 忽略）。顺手修复本地后端 httpx 调用加入 trust_env=False，避免代理环境污染；修复 release_gate MCP wrapper 在 skip_ui=false 时传空字符串参数。同步更新 dev_toolkit/README.md 与 AGENTS.md。验证：python3.14 -m py_compile dev_toolkit/server.py 通过；ruff check dev_toolkit/server.py 通过；python3.14 直接调用 _worktree_guard/_tool_usage_stats/call_tool 分发自测通过；git diff --check 通过。
