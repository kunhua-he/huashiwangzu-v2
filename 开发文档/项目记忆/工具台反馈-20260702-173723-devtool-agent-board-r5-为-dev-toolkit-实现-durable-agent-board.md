---
name: "工具台反馈-20260702-173723-devtool-agent-board-r5-为 dev_toolkit 实现 durable agent board"
type: "reference"
tags: [mcp-feedback, dev-toolkit]
agent: "devtool-agent-board-r5"
created: "2026-07-02T17:37:23.423783+00:00"
---

# MCP 使用反馈

## 任务

为 dev_toolkit 实现 durable agent board 最小可用版，支持多子代理任务 claim/heartbeat/complete/block/snapshot 本地持久化。

## 顺畅度

- 评分：4/5
- 体感：整体顺畅，组件化规范清晰，stdio entry 测试能快速证明新工具会被 MCP 自动发现。

## 本次用到的工具

brief, plan_task, worktree_guard, code_explore, code_node, code_impact, lint, finish_task, mcp_self_check, memory_write, mcp_feedback

## 卡点 / 不顺手的地方

`lint` 工具传逗号多路径时被当成单一路径，直接 ruff 命令可绕过；全局并行 worker 脏改会让严格 allowed_prefixes 的 worktree_guard 报越界，需要按实际 agent 边界解释。

## 缺少的工具 / 能力

新工具上线前没有可用的持久化 agent board；本轮已补。

## 升级建议

后续可让 agent_board 支持 claim 队列模板、parent/child task、heartbeat stale 自动报告，并接入 brief() 的最近 agent board 摘要。

## 建议移除或合并的工具

无

## 其他备注

状态文件设计为 backend/logs/agent_board.json，测试使用 tmp_path 未污染真实状态；新 MCP 工具需要 MCP server 重载后才能在当前工具 namespace 中直接调用。

## 当前工具热度快照

```json
[
  {
    "tool": "code_node",
    "calls": 412,
    "error": 0,
    "avg_duration_seconds": 0.145
  },
  {
    "tool": "lint",
    "calls": 271,
    "error": 0,
    "avg_duration_seconds": 0.016
  },
  {
    "tool": "code_explore",
    "calls": 209,
    "error": 0,
    "avg_duration_seconds": 0.317
  },
  {
    "tool": "sql",
    "calls": 207,
    "error": 8,
    "avg_duration_seconds": 0.031
  },
  {
    "tool": "worktree_guard",
    "calls": 139,
    "error": 0,
    "avg_duration_seconds": 0.031
  },
  {
    "tool": "code_impact",
    "calls": 134,
    "error": 0,
    "avg_duration_seconds": 0.139
  },
  {
    "tool": "db_schema",
    "calls": 129,
    "error": 0,
    "avg_duration_seconds": 0.033
  },
  {
    "tool": "run_test",
    "calls": 124,
    "error": 0,
    "avg_duration_seconds": 2.577
  },
  {
    "tool": "probe",
    "calls": 111,
    "error": 0,
    "avg_duration_seconds": 0.507
  },
  {
    "tool": "plan_task",
    "calls": 95,
    "error": 0,
    "avg_duration_seconds": 0.007
  }
]
```
