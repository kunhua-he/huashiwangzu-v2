---
name: "工具台反馈-20260702-142237-codex-memory-profile-audit-explorer-审计 modules/memory 与 agent.profile_ev"
type: "reference"
tags: [mcp-feedback, dev-toolkit]
agent: "codex-memory-profile-audit-explorer"
created: "2026-07-02T14:22:37.411937+00:00"
---

# MCP 使用反馈

## 任务

审计 modules/memory 与 agent.profile_evolve 任务链路，只探查不改代码

## 顺畅度

- 评分：4/5
- 体感：整体顺畅，CodeGraph + SQL + capability probe 能快速拼出链路和运行态。

## 本次用到的工具

brief, plan_task, worktree_guard, code_explore, code_node, routes, capabilities, db_schema, sql, probe, call_capability, tail_log, finish_task, memory_write, mcp_feedback

## 卡点 / 不顺手的地方

code_node 对纯测试文件有时不索引，需要退回 sed；finish_task 显示的 dirty 文件是其他任务改动，容易和本次只读审计混淆。

## 缺少的工具 / 能力

希望有 task_queue_audit 的可参数化 MCP 工具，直接按 task_type/error_message 归档候选和重跑候选分组。

## 升级建议

SQL 输出建议保留字段名而不是 col0/col1，审计报告粘贴会更稳。

## 建议移除或合并的工具

无

## 其他备注

本次未改产品代码。

## 当前工具热度快照

```json
[
  {
    "tool": "code_node",
    "calls": 182,
    "error": 0,
    "avg_duration_seconds": 0.139
  },
  {
    "tool": "lint",
    "calls": 146,
    "error": 0,
    "avg_duration_seconds": 0.016
  },
  {
    "tool": "sql",
    "calls": 137,
    "error": 5,
    "avg_duration_seconds": 0.031
  },
  {
    "tool": "code_explore",
    "calls": 102,
    "error": 0,
    "avg_duration_seconds": 0.303
  },
  {
    "tool": "worktree_guard",
    "calls": 54,
    "error": 0,
    "avg_duration_seconds": 0.029
  },
  {
    "tool": "probe",
    "calls": 46,
    "error": 0,
    "avg_duration_seconds": 0.479
  },
  {
    "tool": "db_schema",
    "calls": 45,
    "error": 0,
    "avg_duration_seconds": 0.033
  },
  {
    "tool": "code_impact",
    "calls": 42,
    "error": 0,
    "avg_duration_seconds": 0.133
  },
  {
    "tool": "routes",
    "calls": 40,
    "error": 0,
    "avg_duration_seconds": 0.058
  },
  {
    "tool": "plan_task",
    "calls": 38,
    "error": 0,
    "avg_duration_seconds": 0.008
  }
]
```
