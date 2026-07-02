---
name: "项目工具台 MCP 一次性组件化重构"
type: "architecture"
tags: [mcp, dev-toolkit, architecture, componentization]
agent: "codex"
created: "2026-07-02T08:44:04.644583+00:00"
---

本次按项目级重构方式继续拆分 dev_toolkit/server.py：新增 memory_tools.py、worktree_tools.py、tool_usage_tools.py，并保留已拆的 mailbox_tools.py。server.py 现在只拼接组件 tool_definitions 并用 handles_tool/handle_tool 做顶层路由；memory/mcp_feedback/tool_usage/worktree/mailbox 均已组件化。server.py 行数降到 2182。验证：py_compile、ruff、git diff --check、list_tools 无重复、关键组件 call_tool 自测、fallback import 自测均通过。残留：活系统探测、代码工具、计划收工仍在 server.py，下一步可继续拆 system_probe_tools、code_quality_tools、workflow_tools。
