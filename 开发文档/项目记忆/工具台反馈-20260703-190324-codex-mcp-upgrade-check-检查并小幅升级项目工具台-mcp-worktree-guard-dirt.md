---
name: "工具台反馈-20260703-190324-codex-mcp-upgrade-check-检查并小幅升级项目工具台 MCP：worktree_guard dirt"
type: "reference"
tags: [mcp-feedback, dev-toolkit]
agent: "codex-mcp-upgrade-check"
created: "2026-07-03T19:03:24.486913+00:00"
---

# MCP 使用反馈

## 任务

检查并小幅升级项目工具台 MCP：worktree_guard dirty 归因、tool_job release_safe 口径、finish_task timing_data 耗时表

## 顺畅度

- 评分：5/5
- 体感：整体顺畅；mcp_feedback_summary、tool_usage_stats、mcp_self_check 给出的升级方向很集中，CodeGraph 定位影响面也很快。

## 本次用到的工具

brief, plan_task, worktree_guard, code_explore, code_node, code_impact, lint, run_test, mcp_self_check, finish_task, memory_write, mcp_feedback

## 卡点 / 不顺手的地方

当前 MCP 进程对新落盘 schema 不一定热加载，因此新增字段需要新会话/重启后完整可见；这点容易让现场验证看起来像没生效。

## 缺少的工具 / 能力

缺一个显式的 mcp_reload_or_restart 提示/自检工具，能告诉 agent 当前进程是否已加载最新工具 schema。

## 升级建议

后续可继续做：finish_task 自动比较本轮 timing_data 与历史同类验证耗时；worktree_guard 接入 agent_board/memory 的更明确 dirty 归因。

## 建议移除或合并的工具

无

## 其他备注

本轮合理使用 2 个 explorer 子代理：一个调查 tool_job 语义，一个调查 finish_task timing_data，主线同时实现和验证。

## 当前工具热度快照

```json
[
  {
    "tool": "code_node",
    "calls": 1323,
    "error": 0,
    "avg_duration_seconds": 0.144
  },
  {
    "tool": "lint",
    "calls": 663,
    "error": 0,
    "avg_duration_seconds": 0.031
  },
  {
    "tool": "probe",
    "calls": 575,
    "error": 8,
    "avg_duration_seconds": 0.448
  },
  {
    "tool": "code_explore",
    "calls": 572,
    "error": 0,
    "avg_duration_seconds": 0.326
  },
  {
    "tool": "sql",
    "calls": 566,
    "error": 35,
    "avg_duration_seconds": 0.031
  },
  {
    "tool": "call_capability",
    "calls": 499,
    "error": 17,
    "avg_duration_seconds": 0.681
  },
  {
    "tool": "worktree_guard",
    "calls": 479,
    "error": 0,
    "avg_duration_seconds": 0.03
  },
  {
    "tool": "run_test",
    "calls": 472,
    "error": 3,
    "avg_duration_seconds": 4.411
  },
  {
    "tool": "code_impact",
    "calls": 468,
    "error": 0,
    "avg_duration_seconds": 0.134
  },
  {
    "tool": "db_schema",
    "calls": 371,
    "error": 0,
    "avg_duration_seconds": 0.033
  }
]
```
