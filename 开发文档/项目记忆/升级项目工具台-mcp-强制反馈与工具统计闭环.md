---
name: "升级项目工具台 MCP：强制反馈与工具统计闭环"
type: task
tags: ["mcp", "dev-toolkit", "feedback", "governance"]
created: 2026-07-02
agent: codex
---

本次按用户要求升级项目工具台 MCP：新增 worktree_guard、tool_usage_stats、mcp_feedback、mcp_feedback_summary，并把 finish_task 扩展为返回 memory_write 与 mcp_feedback 两个收工模板。mcp_feedback 会在开发文档/项目记忆/ 下写入结构化 Markdown 反馈，便于后续升级工具台时读取顺畅度、摩擦点、缺失工具、升级建议和移除/合并建议。AGENTS.md 已补充收工必须调用 mcp_feedback(agent="<自己>")；dev_toolkit/README.md 已更新工具清单与收工流程。验证：python3.14 -m py_compile dev_toolkit/server.py 通过；backend/.venv/bin/python -m ruff check dev_toolkit/server.py 通过；git diff --check 通过；直接导入 server.py 自测 mcp_feedback_summary 成功，当前保留 1 条真实反馈记录。注意：当前会话 MCP 已加载的是旧工具列表，新增 tool 需要新 agent 或 MCP 重连后暴露。
