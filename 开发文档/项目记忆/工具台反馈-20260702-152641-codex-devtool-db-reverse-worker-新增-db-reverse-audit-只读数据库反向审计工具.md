---
name: "工具台反馈-20260702-152641-codex-devtool-db-reverse-worker-新增 db_reverse_audit 只读数据库反向审计工具"
type: "reference"
tags: [mcp-feedback, dev-toolkit]
agent: "codex-devtool-db-reverse-worker"
created: "2026-07-02T15:26:41.970466+00:00"
---

# MCP 使用反馈

## 任务

新增 db_reverse_audit 只读数据库反向审计工具

## 顺畅度

- 评分：4/5
- 体感：整体顺畅；ClientSession 调 MCP 比手写 JSON-RPC 稳定。

## 本次用到的工具

brief, plan_task, worktree_guard, code_explore, code_node, code_impact, finish_task, memory_write, mcp_feedback, db_reverse_audit

## 卡点 / 不顺手的地方

工作区已有大量 dirty 文件，diff 中混有其他 agent 对 server.py/README.md 的既有组件化改动，归因需要额外小心。

## 缺少的工具 / 能力

希望 worktree_guard/finish_task 支持 allowed_prefixes，这样框架工具台任务能更准确区分本任务边界。

## 升级建议

db_reverse_audit 后续可增加基于历史真实数据的 table-owner 规则反馈入口。

## 建议移除或合并的工具

无

## 其他备注

无

## 当前工具热度快照

```json
[
  {
    "tool": "code_node",
    "calls": 202,
    "error": 0,
    "avg_duration_seconds": 0.14
  },
  {
    "tool": "lint",
    "calls": 190,
    "error": 0,
    "avg_duration_seconds": 0.016
  },
  {
    "tool": "sql",
    "calls": 154,
    "error": 7,
    "avg_duration_seconds": 0.031
  },
  {
    "tool": "code_explore",
    "calls": 132,
    "error": 0,
    "avg_duration_seconds": 0.305
  },
  {
    "tool": "worktree_guard",
    "calls": 72,
    "error": 0,
    "avg_duration_seconds": 0.029
  },
  {
    "tool": "code_impact",
    "calls": 64,
    "error": 0,
    "avg_duration_seconds": 0.131
  },
  {
    "tool": "run_test",
    "calls": 63,
    "error": 0,
    "avg_duration_seconds": 3.423
  },
  {
    "tool": "db_schema",
    "calls": 56,
    "error": 0,
    "avg_duration_seconds": 0.033
  },
  {
    "tool": "probe",
    "calls": 56,
    "error": 0,
    "avg_duration_seconds": 0.474
  },
  {
    "tool": "plan_task",
    "calls": 50,
    "error": 0,
    "avg_duration_seconds": 0.008
  }
]
```
