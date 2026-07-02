---
name: "项目工具台 MCP 组件化路由模式"
type: architecture
tags: ["mcp", "dev-toolkit", "architecture", "mailbox", "refactor"]
created: 2026-07-02
agent: codex
---

本次在标准化邮箱投递信/回信五件套后，进一步按用户反馈改成组件化路由模式：dev_toolkit/server.py 只保留 MCP 启动、通用上下文、工具列表拼接和顶层路由；邮箱工具迁入 dev_toolkit/mailbox_tools.py，组件提供 tool_definitions()、handles_tool(name)、handle_tool(repo_root, name, arguments)。旧别名 写封信 也迁入邮箱组件，server.py 不再维护邮箱 schema 或邮箱 if/elif 分支。当前 server.py 行数降到 2873，mailbox_tools.py 为 502 行。文档已在 dev_toolkit/README.md 写入组件化结构，并在 AGENTS.md 加硬规则：新增 MCP 工具必须组件化。验证：py_compile 通过；ruff 通过；git diff --check 通过；直接调用 list_tools、写封信、mailbox_create_delivery_bundle、mailbox_check_delivery_bundle 成功，测试产物已清理。残留：server.py 仍偏大，下一批建议迁移 memory_tools、worktree_tools、system_probe_tools 和 tool_catalog/core routing。
