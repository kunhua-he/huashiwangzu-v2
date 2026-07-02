---
name: "工具台反馈-20260702-082832-codex-标准化邮箱投递信和回信五件套 MCP，并拆分 server.py 中的邮"
type: "reference"
tags: [mcp-feedback, dev-toolkit]
agent: "codex"
created: "2026-07-02T08:28:32.341910+00:00"
---

# MCP 使用反馈

## 任务

标准化邮箱投递信和回信五件套 MCP，并拆分 server.py 中的邮箱实现

## 顺畅度

- 评分：4/5
- 体感：整体顺畅；直接自测新工具能覆盖真实写信、五件套生成和检查链路。中途发现 server.py 过大后已先拆出 mailbox_tools.py。

## 本次用到的工具

codegraph CLI, py_compile, ruff, mailbox_write_letter, mailbox_create_delivery_bundle, mailbox_check_delivery_bundle, mcp_feedback

## 卡点 / 不顺手的地方

当前会话仍需直接导入 server.py 自测新增 MCP 工具；server.py 仍有 2968 行，后续应继续拆 tool_catalog、memory_tools、worktree_tools。

## 缺少的工具 / 能力

缺少一键检测 dev_toolkit/server.py 分模块体积和建议拆分边界的工具。

## 升级建议

下一轮把 list_tools/schema 注册拆到 tool_catalog.py，把 memory/mcp_feedback 和 worktree/git guard 也拆成独立模块。

## 建议移除或合并的工具

保留旧别名 写封信，但长期可在所有 agent 切到 mailbox_write_letter 后降级为兼容入口。

## 其他备注

测试过程生成的测试信和测试五件套已清理。

## 当前工具热度快照

```json
[
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
    "tool": "mailbox_check_delivery_bundle",
    "calls": 1,
    "error": 0,
    "avg_duration_seconds": 0.0
  },
  {
    "tool": "mailbox_create_delivery_bundle",
    "calls": 1,
    "error": 0,
    "avg_duration_seconds": 0.002
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
  }
]
```
