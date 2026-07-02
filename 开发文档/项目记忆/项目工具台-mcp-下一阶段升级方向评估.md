---
name: "项目工具台 MCP 下一阶段升级方向评估"
type: "task"
tags: [mcp, dev-toolkit, upgrade, precise-edit]
agent: "codex"
created: "2026-07-02T09:04:40.823979+00:00"
---

# 结论

项目工具台 MCP 还能继续升级，重点不是再堆工具数量，而是把现有闭环变得更好用、更可维护、更自解释。

# 当前已有能力

- `tool_usage_stats` 已记录工具调用计数、成功失败和耗时。
- `mcp_feedback` / `mcp_feedback_summary` 已收集每次任务的主观体验、卡点和升级建议。
- `mailbox_write_letter`、`mailbox_create_delivery_bundle`、`mailbox_check_delivery_bundle` 已形成发信/回信五件套闭环。
- `quick_fix_preview` / `quick_fix_patch` 已支持精准 old_text 唯一命中替换、sha256 防漂移、原子写盘。

# 建议升级方向

1. 新增 `mcp_self_check` / `dev_toolkit_architecture_audit`：统计服务端工具数、组件覆盖率、重复工具名、server.py 行数、是否有工具未组件化，并提示重启后需要 `tool_search` 加载延迟工具。
2. 升级精准编辑为分层引擎：默认 quick_fix 精确文本块；复杂场景可选 ast-grep 结构化替换；Python 大规模 codemod 可选 LibCST；先做预览、唯一命中、安全边界、再写盘。
3. 新增 `edit_recipe_preview/apply`：把常见安全改法做成 recipe，所有 recipe 必须有预览 diff、影响面、lint/test 建议。
4. 新增 `agent_activity_report`：按 agent 汇总谁用了哪些 MCP、成功率、反馈评分、发了哪些信、执行了哪些回信、提出了什么升级建议。
5. 继续组件化，控制单文件大小：把 server.py 中 system/workflow/tool-catalog 等残留能力拆成 `*_tools.py`，每个组件保持 tool_definitions/handles_tool/handle_tool 三件套。

# 外部方案定位

- ast-grep：适合跨语言 AST 结构搜索/替换。
- LibCST：适合 Python 保格式 codemod。
- Tree-sitter：适合作为多语言语法树底座，但不建议第一步直接深度集成。
- OpenRewrite：适合 Java/大规模 recipe 思路借鉴，本项目当前栈不建议直接引入。

# 残留风险

不要一次性引入重依赖；先保留 quick_fix 小而稳的路径，再按语言/场景逐层扩展。
