---
name: "项目工具台 MCP 小幅升级：dirty 归因、job 语义、收工耗时表"
type: "task"
tags: [dev-toolkit, mcp, worktree-guard, tool-job, finish-task, testing]
agent: "codex-mcp-upgrade-check"
created: "2026-07-03T19:03:23.703719+00:00"
---

# 改了什么
- 检查近期 MCP 反馈和工具台健康后，确认无紧急故障，但多 agent dirty 归因、tool_job release gate 字段语义、finish_task 外部验证耗时表值得小幅升级。
- `worktree_guard` 新增 `changed_entries` 和 `*_by_group` 分组字段，用于区分本轮新增 dirty、基线承认 dirty、越界/禁止路径风险。
- `tool_job_tools` 对齐 release gate 口径：`PASS_WITH_DEBT` 且 returncode=0 时，即使摘要缺 `release_safe`，也推导 `release_safe=true`、`clean_success=false`。
- `finish_task` 新增可选 `timing_data` JSON 输入，并输出 `test_timing`；自身运行的 `test_targets` 会自动追加耗时条目。
- README 补充上述字段和 `tool_job_status` 的 `command_success/clean_success/release_safe` 语义。

# 验证了什么
- ruff 检查 9 个相关 Python 文件全绿。
- pytest `dev_toolkit/test_worktree_tools.py dev_toolkit/test_tool_job_tools.py dev_toolkit/test_timing_tools.py dev_toolkit/test_server_helpers.py`：64 passed。
- `mcp_self_check`：success=true，入口匹配，无重复/孤儿工具。
- `finish_task`：success=true，边界检查通过。

# 是否还有残留风险
- 当前已运行的 MCP 进程可能需要新会话/重启后才完全暴露新增 schema 字段；后续新会话会复用落盘代码和 README 规则。
- 工作区存在本任务前测试加速专项留下的 dirty 文件，未回退。

# 关联 commit
- 未提交。
