---
name: "项目工具台 MCP 入口声明与组件化注册修复"
type: "task"
tags: [dev-toolkit, mcp, entrypoint, componentization, 20260702]
agent: "codex-dev-toolkit-repair-worker"
created: "2026-07-02T14:46:08.633756+00:00"
---

# 改了什么

- 新增 `dev_toolkit/mcp_entry.py`，统一 `.mcp.json` 与 `server.py` 的 MCP 入口元数据和校验。
- 新增 `dev_toolkit/core_tools.py`，把原先 `server.py` 内联的核心工具 schema 与顶层分发收口到组件三件套。
- `server.py` 改为通过 `core_tools` 注册/分发核心工具，并使用 `SERVER_NAME` / `SERVER_VERSION`。
- `.mcp.json` 增加显式 `cwd`，标准 MCP 自动发现后不依赖调用方当前目录。
- `mcp_self_check` 增加入口声明校验，且确认 server.py direct tool count 为 0。
- `mailbox_tools.py` 不再公开非 ASCII 旧别名 `写封信`，避免标准 MCP tools/list 工具名警告；服务端仍兼容该旧调用。
- README 与 `开发文档/README.md` 同步两套入口口径。

# 验证了什么

- `backend/.venv/bin/ruff check dev_toolkit/server.py dev_toolkit/core_tools.py dev_toolkit/mcp_entry.py dev_toolkit/insight_tools.py dev_toolkit/mailbox_tools.py dev_toolkit/test_insight_tools.py dev_toolkit/test_mcp_entry.py`：通过。
- `backend/.venv/bin/python -m pytest dev_toolkit/test_mcp_entry.py dev_toolkit/test_insight_tools.py dev_toolkit/test_server_helpers.py`：1 passed / 2 skipped（后端 venv 缺 mcp 包）。
- `python3.14 dev_toolkit/server.py` MCP initialize + tools/list：serverInfo 为 `项目工具台` 1.0.0，公开 50 tools，0 duplicate，旧中文别名未公开。
- `mcp_self_check`：success=true，entrypoint_success=true，component_count=8，direct_tool_count=0，component_tool_count=50。
- 全量 `backend/.venv/bin/python -m pytest dev_toolkit` 跑到 17 passed / 2 skipped 后 187.82s 人工中断慢路径。

# 是否还有残留风险

`server.py` 仍保留历史实现函数且超过 600 行；本次先修入口声明、schema 注册和顶层分发，后续可继续把实现按 core 工具组迁移出 server.py。共享工作区存在其他 agent 的 backend/modules/dev_toolkit 改动，本任务未回退。
