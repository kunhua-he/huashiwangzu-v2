---
name: "项目工具台 MCP 组件化重构第二阶段-code-tools"
type: "architecture"
tags: [mcp, dev-toolkit, architecture, code-tools]
agent: "codex"
created: "2026-07-02T08:50:33.446055+00:00"
---

继续按组件化路由模式拆分 dev_toolkit/server.py：新增 dev_toolkit/code_tools.py，迁移 code_explore、code_node、code_impact、quick_fix_preview、quick_fix_patch、apply_patch、lint、run_test。server.py 现在通过 code_tool_definitions() 拼工具列表，通过 code_handles_tool/code_handle_tool 分发代码工具；finish_task 复用 code_lint/code_run_test。当前 server.py 降到 1869 行。验证：py_compile、ruff、git diff --check、list_tools duplicate_count=0、lint/memory_recent/worktree_guard 组件调用成功、fallback import 成功。
