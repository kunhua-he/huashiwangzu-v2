---
name: "一次性升级项目工具台 MCP：自检、活动报告、批量精准编辑与 recipe 编辑"
type: "task"
tags: [mcp, dev-toolkit, precise-edit, agent-activity, self-check]
agent: "codex"
created: "2026-07-02T09:24:08.082381+00:00"
---

# 改了什么

新增 `dev_toolkit/edit_tools.py`，提供确定性轻量编辑 worker：

- `batch_quick_fix_preview`：并发预览多个精准 old_text -> new_text 替换，只读不写盘。
- `batch_quick_fix_apply`：先全量 preview，全部通过后并发原子写盘，可选 lint/test。
- `edit_recipe_catalog`：列出 recipe。
- `edit_recipe_preview` / `edit_recipe_apply`：支持 exact_replace、batch_exact_replace、delete_exact、insert_after、replace_between_markers。

新增 `dev_toolkit/insight_tools.py`，提供工具台洞察：

- `mcp_self_check`：统计工具数、组件覆盖、重复工具名、长文件和延迟加载提示。
- `dev_toolkit_architecture_audit`：工具台组件化审计。
- `agent_activity_report`：按 agent 聚合项目记忆、MCP 反馈、声明使用工具、邮箱交付元信息和升级建议。

升级 `dev_toolkit/tool_usage_tools.py`：

- 保留全局工具热度统计。
- 增加 best-effort agent 归因：从工具参数里的 `agent` / `caller_agent` / `executed_by` 推断，推断不到记为 `unknown`。
- 增加最近调用尾巴 `recent_calls`。

接入 `dev_toolkit/server.py`：

- 注册 edit_tools 与 insight_tools。
- `record_tool_usage` 现在接收 arguments 做归因。

更新 `dev_toolkit/README.md`：

- 补充新组件、新工具、批量精准编辑边界和轻量 worker 说明。

新增测试：

- `dev_toolkit/test_edit_tools.py`
- `dev_toolkit/test_insight_tools.py`

# 验证了什么

- `python3.14 -m py_compile dev_toolkit/edit_tools.py dev_toolkit/insight_tools.py dev_toolkit/tool_usage_tools.py dev_toolkit/server.py dev_toolkit/test_edit_tools.py dev_toolkit/test_insight_tools.py` 通过。
- `backend/.venv/bin/ruff check dev_toolkit/edit_tools.py dev_toolkit/insight_tools.py dev_toolkit/tool_usage_tools.py dev_toolkit/server.py dev_toolkit/test_edit_tools.py dev_toolkit/test_insight_tools.py` 通过。
- `backend/.venv/bin/python -m pytest dev_toolkit/test_server_helpers.py dev_toolkit/test_quick_fix.py dev_toolkit/test_edit_tools.py dev_toolkit/test_insight_tools.py` 返回 8 passed / 2 skipped（backend venv 缺 mcp，沿用旧测试跳过模式）。
- `python3.14` 直接调用 `mcp_self_check` / `agent_activity_report` 成功，显示 51 个工具、7 个组件。
- 本地导入 `server.list_tools()` 返回 51 个工具，包含 8 个新增工具。
- 本地 `server.call_tool()` 调 `edit_recipe_catalog`、`mcp_self_check`、`agent_activity_report` 成功。
- 本地 `server.call_tool()` 对 `batch_quick_fix_preview/apply` 做临时文件探针成功，临时文件已清理。

# 是否还有残留风险

当前正在运行的 MCP server 不会热加载新增工具；需要重启会话或重连 MCP 后，`tool_search` 才能发现 8 个新工具。

MCP 协议本身没有直接提供调用者 agent 身份，所以 per-agent 工具使用统计是 best-effort。能从参数推断就归因，不能就记为 `unknown`；更可靠的归因仍来自 `memory_write` / `mcp_feedback` 的 `agent` 字段。

当前工作区已有大量非 dev_toolkit 未提交改动，本次只新增/修改工具台相关文件和本条记忆/反馈，没有回退或改动既有业务文件。

# 关联 commit

无。
