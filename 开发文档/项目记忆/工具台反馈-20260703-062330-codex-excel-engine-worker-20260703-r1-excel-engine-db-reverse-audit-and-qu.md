---
name: "工具台反馈-20260703-062330-codex-excel-engine-worker-20260703-r1-excel-engine DB reverse audit and qu"
type: "reference"
tags: [mcp-feedback, dev-toolkit]
agent: "codex-excel-engine-worker-20260703-r1"
created: "2026-07-03T06:23:30.131205+00:00"
---

# MCP 使用反馈

## 任务

excel-engine DB reverse audit and quality upgrade for workbook/import/update/append/undo/redo/history/version/compile chains.

## 顺畅度

- 评分：4/5
- 体感：整体顺畅，code_explore/db_reverse_audit/finish_task 能快速锁定空表和边界问题。

## 本次用到的工具

brief, plan_task, worktree_guard, code_explore, code_node, code_impact, routes, capabilities, db_schema, db_reverse_audit, sql, probe, call_capability, lint, tail_log, finish_task, memory_write, agent_board_claim/heartbeat

## 卡点 / 不顺手的地方

finish_task 在多人共享脏工作区中只能全局判边界失败，无法表达“本 agent 新增 diff 只在 module 内”的通过状态。

## 缺少的工具 / 能力

希望 worktree_guard/finish_task 支持 baseline 快照或 since-claim diff，用于多人并行仓库的模块边界验收。

## 升级建议

agent_board_claim 时可自动记录 dirty baseline，finish_task 再比对新增/变化文件，这样模块 worker 不会被其他 agent 的文件误伤。

## 建议移除或合并的工具

无

## 其他备注

call_capability 对 handler 返回 success:false 的兼容有用；但 handler 抛 ValueError 会变 500，本次据此保留 compile_xlsx 的结构化失败返回。

## 当前工具热度快照

```json
[
  {
    "tool": "code_node",
    "calls": 613,
    "error": 0,
    "avg_duration_seconds": 0.145
  },
  {
    "tool": "lint",
    "calls": 447,
    "error": 0,
    "avg_duration_seconds": 0.019
  },
  {
    "tool": "code_explore",
    "calls": 292,
    "error": 0,
    "avg_duration_seconds": 0.325
  },
  {
    "tool": "sql",
    "calls": 272,
    "error": 13,
    "avg_duration_seconds": 0.031
  },
  {
    "tool": "run_test",
    "calls": 228,
    "error": 2,
    "avg_duration_seconds": 3.348
  },
  {
    "tool": "worktree_guard",
    "calls": 227,
    "error": 0,
    "avg_duration_seconds": 0.031
  },
  {
    "tool": "code_impact",
    "calls": 207,
    "error": 0,
    "avg_duration_seconds": 0.137
  },
  {
    "tool": "db_schema",
    "calls": 184,
    "error": 0,
    "avg_duration_seconds": 0.033
  },
  {
    "tool": "probe",
    "calls": 165,
    "error": 2,
    "avg_duration_seconds": 0.469
  },
  {
    "tool": "plan_task",
    "calls": 157,
    "error": 0,
    "avg_duration_seconds": 0.007
  }
]
```
