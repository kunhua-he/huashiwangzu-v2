---
name: "工具台反馈-20260702-084404-codex-项目工具台 MCP 一次性组件化重构：抽 memory/worktree"
type: "reference"
tags: [mcp-feedback, dev-toolkit]
agent: "codex"
created: "2026-07-02T08:44:04.680090+00:00"
---

# MCP 使用反馈

## 任务

项目工具台 MCP 一次性组件化重构：抽 memory/worktree/tool_usage/mailbox 组件

## 顺畅度

- 评分：4/5
- 体感：组件接口清楚后明显更顺；tool_definitions + handles_tool + handle_tool 让主路由更稳定。

## 本次用到的工具

codegraph CLI, apply_patch, py_compile, ruff, memory_write, mcp_feedback, worktree_guard, tool_usage_stats

## 卡点 / 不顺手的地方

server.py 仍有 2182 行，因为 system/code/workflow 三组尚未迁移；但核心模式已经立住。

## 缺少的工具 / 能力

建议新增 dev_toolkit_architecture_audit，自动统计未组件化工具和 server.py 行数趋势。

## 升级建议

下一批继续迁 system_probe_tools、code_quality_tools、workflow_tools，并引入统一 component registry。

## 建议移除或合并的工具

暂不移除旧别名 写封信；作为兼容入口保留。

## 其他备注

关键组件路由和 fallback import 已自测。

## 当前工具热度快照

```json
[
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
    "tool": "tool_usage_stats",
    "calls": 3,
    "error": 0,
    "avg_duration_seconds": 0.0
  },
  {
    "tool": "worktree_guard",
    "calls": 3,
    "error": 0,
    "avg_duration_seconds": 0.026
  },
  {
    "tool": "mailbox_write_letter",
    "calls": 2,
    "error": 0,
    "avg_duration_seconds": 0.001
  },
  {
    "tool": "mcp_feedback_summary",
    "calls": 2,
    "error": 0,
    "avg_duration_seconds": 0.001
  },
  {
    "tool": "mcp_feedback",
    "calls": 1,
    "error": 0,
    "avg_duration_seconds": 0.022
  },
  {
    "tool": "memory_recent",
    "calls": 1,
    "error": 0,
    "avg_duration_seconds": 0.007
  },
  {
    "tool": "memory_write",
    "calls": 1,
    "error": 0,
    "avg_duration_seconds": 0.036
  },
  {
    "tool": "写封信",
    "calls": 1,
    "error": 0,
    "avg_duration_seconds": 0.001
  }
]
```
