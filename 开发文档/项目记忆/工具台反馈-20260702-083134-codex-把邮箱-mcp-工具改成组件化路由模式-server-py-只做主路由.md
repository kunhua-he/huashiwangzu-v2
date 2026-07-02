---
name: "工具台反馈-20260702-083134-codex-把邮箱 MCP 工具改成组件化路由模式，server.py 只做主路由"
type: "reference"
tags: [mcp-feedback, dev-toolkit]
agent: "codex"
created: "2026-07-02T08:31:34.058529+00:00"
---

# MCP 使用反馈

## 任务

把邮箱 MCP 工具改成组件化路由模式，server.py 只做主路由

## 顺畅度

- 评分：4/5
- 体感：组件化后更顺手；邮箱工具的 schema、handles_tool、handle_tool 都集中在 mailbox_tools.py，server.py 只负责展开和路由。

## 本次用到的工具

codegraph CLI, py_compile, ruff, mailbox component direct call, mcp_feedback

## 卡点 / 不顺手的地方

server.py 仍有 2873 行，说明历史工具还没有组件化；但邮箱组已经成为可复制模板。

## 缺少的工具 / 能力

可以补一个 dev_toolkit 拆分健康检查，扫描 server.py 行数、工具 schema 留存和未组件化工具数量。

## 升级建议

下一批拆 tool_catalog/core routing，再迁 memory_tools、worktree_tools、system_probe_tools。

## 建议移除或合并的工具

短期保留 写封信 兼容入口；主推 mailbox_write_letter。

## 其他备注

测试信和测试五件套均已清理。

## 当前工具热度快照

```json
[
  {
    "tool": "mailbox_check_delivery_bundle",
    "calls": 2,
    "error": 0,
    "avg_duration_seconds": 0.0
  },
  {
    "tool": "mailbox_create_delivery_bundle",
    "calls": 2,
    "error": 0,
    "avg_duration_seconds": 0.002
  },
  {
    "tool": "tool_usage_stats",
    "calls": 2,
    "error": 0,
    "avg_duration_seconds": 0.0
  },
  {
    "tool": "worktree_guard",
    "calls": 2,
    "error": 0,
    "avg_duration_seconds": 0.022
  },
  {
    "tool": "mailbox_write_letter",
    "calls": 1,
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
    "tool": "mcp_feedback_summary",
    "calls": 1,
    "error": 0,
    "avg_duration_seconds": 0.001
  },
  {
    "tool": "写封信",
    "calls": 1,
    "error": 0,
    "avg_duration_seconds": 0.001
  }
]
```
