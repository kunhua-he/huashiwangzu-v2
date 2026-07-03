---
name: "工具台反馈-20260703-060849-codex-backend-foundation-worker-20260703-r1-审计并修复 backend/app 与 backend/tests 底层"
type: "reference"
tags: [mcp-feedback, dev-toolkit]
agent: "codex-backend-foundation-worker-20260703-r1"
created: "2026-07-03T06:08:49.084081+00:00"
---

# MCP 使用反馈

## 任务

审计并修复 backend/app 与 backend/tests 底层权限、健康和 private modules runtime 恢复。

## 顺畅度

- 评分：4/5
- 体感：整体顺畅，brief/plan/codegraph/db_reverse/probe/run_test 能串起完整闭环。

## 本次用到的工具

brief, plan_task, worktree_guard, db_reverse_audit, routes, code_explore, code_node, code_impact, probe, lint, run_test, finish_task, memory_write, agent_board_heartbeat

## 卡点 / 不顺手的地方

finish_task 的 test_targets 多目标合并后把聚焦测试和完整 tests 一起跑，结果不够区分；worktree_guard 在多人并行 dirty 时只能报全局红，需要更好展示本 agent touched set。

## 缺少的工具 / 能力

希望有基于 git diff -- pathspec 的 boundary_guard/touched_files 参数，用来在多人并行工作树里验收当前 agent 范围。

## 升级建议

finish_task 支持 separate_test_results：required_targets 与 informational_full_suite 分开判定；worktree_guard 支持 allowed_prefixes 且标注 outside dirty 是否早于本 agent claim。

## 建议移除或合并的工具

无

## 其他备注

本次 codegraph 对定位 check_file_access 与 private_module_service 影响面很有用；db_reverse_audit 对空表优先级判断有效。

## 当前工具热度快照

```json
[
  {
    "tool": "code_node",
    "calls": 576,
    "error": 0,
    "avg_duration_seconds": 0.145
  },
  {
    "tool": "lint",
    "calls": 428,
    "error": 0,
    "avg_duration_seconds": 0.017
  },
  {
    "tool": "code_explore",
    "calls": 285,
    "error": 0,
    "avg_duration_seconds": 0.325
  },
  {
    "tool": "sql",
    "calls": 271,
    "error": 13,
    "avg_duration_seconds": 0.031
  },
  {
    "tool": "run_test",
    "calls": 220,
    "error": 2,
    "avg_duration_seconds": 3.333
  },
  {
    "tool": "worktree_guard",
    "calls": 220,
    "error": 0,
    "avg_duration_seconds": 0.031
  },
  {
    "tool": "code_impact",
    "calls": 195,
    "error": 0,
    "avg_duration_seconds": 0.138
  },
  {
    "tool": "db_schema",
    "calls": 174,
    "error": 0,
    "avg_duration_seconds": 0.033
  },
  {
    "tool": "plan_task",
    "calls": 154,
    "error": 0,
    "avg_duration_seconds": 0.007
  },
  {
    "tool": "probe",
    "calls": 153,
    "error": 0,
    "avg_duration_seconds": 0.45
  }
]
```
