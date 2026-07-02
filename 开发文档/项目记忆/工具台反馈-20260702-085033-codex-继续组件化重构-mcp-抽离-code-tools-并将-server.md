---
name: "工具台反馈-20260702-085033-codex-继续组件化重构 MCP：抽离 code_tools 并将 server."
type: "reference"
tags: [mcp-feedback, dev-toolkit]
agent: "codex"
created: "2026-07-02T08:50:33.474734+00:00"
---

# MCP 使用反馈

## 任务

继续组件化重构 MCP：抽离 code_tools 并将 server.py 降到 1869 行

## 顺畅度

- 评分：4/5
- 体感：组件化模式清楚，迁移 code tools 后主路由更像壳了；finish_task 也能复用代码组件。

## 本次用到的工具

codegraph CLI, apply_patch, py_compile, ruff, lint component, memory_write, mcp_feedback

## 卡点 / 不顺手的地方

完整拆 system/workflow 仍需要下一步，但本轮已迁出 mailbox/memory/worktree/tool_usage/code 五组高频工具。

## 缺少的工具 / 能力

建议新增组件健康检查：统计 server.py 行数、组件工具覆盖率、重复 tool name。

## 升级建议

下一步拆 system_tools 和 workflow_tools，并加统一组件 registry，减少 server.py 手写 if/elif。

## 建议移除或合并的工具

无。

## 其他备注

所有测试产物已清理。

## 当前工具热度快照

```json
[
  {
    "tool": "tool_usage_stats",
    "calls": 4,
    "error": 0,
    "avg_duration_seconds": 0.0
  },
  {
    "tool": "worktree_guard",
    "calls": 4,
    "error": 0,
    "avg_duration_seconds": 0.025
  },
  {
    "tool": "mailbox_check_delivery_bundle",
    "calls": 3,
    "error": 0,
    "avg_duration_seconds": 0.0
  },
  {
    "tool": "mailbox_create_delivery_bundle",
    "calls": 3,
    "error": 0,
    "avg_duration_seconds": 0.001
  },
  {
    "tool": "lint",
    "calls": 2,
    "error": 0,
    "avg_duration_seconds": 0.013
  },
  {
    "tool": "mailbox_write_letter",
    "calls": 2,
    "error": 0,
    "avg_duration_seconds": 0.001
  },
  {
    "tool": "mcp_feedback",
    "calls": 2,
    "error": 0,
    "avg_duration_seconds": 0.015
  },
  {
    "tool": "mcp_feedback_summary",
    "calls": 2,
    "error": 0,
    "avg_duration_seconds": 0.001
  },
  {
    "tool": "memory_recent",
    "calls": 2,
    "error": 0,
    "avg_duration_seconds": 0.007
  },
  {
    "tool": "memory_write",
    "calls": 2,
    "error": 0,
    "avg_duration_seconds": 0.033
  }
]
```
