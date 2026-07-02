---
name: "工具台反馈-20260702-123616-Knowledge-K1-Repair knowledge pipeline degraded/f"
type: "reference"
tags: [mcp-feedback, dev-toolkit]
agent: "Knowledge-K1"
created: "2026-07-02T12:36:16.915957+00:00"
---

# MCP 使用反馈

## 任务

Repair knowledge pipeline degraded/failed semantics for raw/fusion/orchestrator.

## 顺畅度

- 评分：4/5
- 体感：MCP stdio was usable after manual Python client setup; codegraph CLI was useful. Direct MCP tools were not injected in the chat namespace, so workflow calls happened late.

## 本次用到的工具

codegraph CLI, worktree_guard, finish_task, memory_write, mcp_feedback, ruff, pytest

## 卡点 / 不顺手的地方

Had to invoke dev_toolkit/server.py through Python MCP client. Parallel workers left unrelated dirty files, making module boundary guard globally red.

## 缺少的工具 / 能力

Direct exposed project-toolkit MCP functions in chat tool namespace.

## 升级建议

Add a lightweight CLI wrapper for brief/plan_task/worktree_guard/finish_task/memory_write/mcp_feedback.

## 建议移除或合并的工具

None.

## 其他备注

无

## 当前工具热度快照

```json
[
  {
    "tool": "code_node",
    "calls": 137,
    "error": 0,
    "avg_duration_seconds": 0.14
  },
  {
    "tool": "lint",
    "calls": 137,
    "error": 0,
    "avg_duration_seconds": 0.016
  },
  {
    "tool": "sql",
    "calls": 109,
    "error": 3,
    "avg_duration_seconds": 0.031
  },
  {
    "tool": "code_explore",
    "calls": 79,
    "error": 0,
    "avg_duration_seconds": 0.304
  },
  {
    "tool": "worktree_guard",
    "calls": 48,
    "error": 0,
    "avg_duration_seconds": 0.03
  },
  {
    "tool": "probe",
    "calls": 43,
    "error": 0,
    "avg_duration_seconds": 0.492
  },
  {
    "tool": "db_schema",
    "calls": 37,
    "error": 0,
    "avg_duration_seconds": 0.034
  },
  {
    "tool": "code_impact",
    "calls": 35,
    "error": 0,
    "avg_duration_seconds": 0.134
  },
  {
    "tool": "routes",
    "calls": 33,
    "error": 0,
    "avg_duration_seconds": 0.057
  },
  {
    "tool": "plan_task",
    "calls": 32,
    "error": 0,
    "avg_duration_seconds": 0.007
  }
]
```
