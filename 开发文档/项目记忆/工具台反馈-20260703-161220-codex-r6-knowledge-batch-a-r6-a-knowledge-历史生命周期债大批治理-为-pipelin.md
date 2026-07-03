---
name: "工具台反馈-20260703-161220-codex-r6-knowledge-batch-a-R6-A knowledge 历史生命周期债大批治理：为 pipelin"
type: "reference"
tags: [mcp-feedback, dev-toolkit]
agent: "codex-r6-knowledge-batch-a"
created: "2026-07-03T16:12:20.397498+00:00"
---

# MCP 使用反馈

## 任务

R6-A knowledge 历史生命周期债大批治理：为 pipeline-debt apply/dry-run 增加 category/category_limits/limit_each/order 稳定选择与 capability dry-run 通路。

## 顺畅度

- 评分：4/5
- 体感：整体顺畅，brief/plan/guard/codegraph/probe/call_capability 能串起完整开发和活栈验证。

## 本次用到的工具

brief, plan_task, worktree_guard, code_explore, code_node, code_impact, routes, capabilities, db_schema, lint, run_test, probe, call_capability, finish_task, memory_write, mcp_feedback

## 卡点 / 不顺手的地方

多 worker 并发 dirty 会让 finish_task/worktree_guard 报当前任务边界失败，缺少按“本 agent 实际 touched files”自动归因的视图；probe 大响应裁剪时默认预览可能隐藏新增字段，需要 selector 二次确认。

## 缺少的工具 / 能力

希望有一个 git touched-by-agent 或 diff-scope 快照工具，能在开工 baseline 后区分并发 worker 新增 dirty；希望 probe 支持返回指定多个 selector 的小摘要。

## 升级建议

finish_task 可接受 start guard token 并自动标注 concurrent dirty；probe/call_capability 可在截断 preview 中优先保留新字段或用户指定字段。

## 建议移除或合并的工具

无。

## 其他备注

按要求未执行生产 apply，仅 dry-run。

## 当前工具热度快照

```json
[
  {
    "tool": "code_node",
    "calls": 1197,
    "error": 0,
    "avg_duration_seconds": 0.144
  },
  {
    "tool": "lint",
    "calls": 642,
    "error": 0,
    "avg_duration_seconds": 0.03
  },
  {
    "tool": "sql",
    "calls": 515,
    "error": 25,
    "avg_duration_seconds": 0.031
  },
  {
    "tool": "probe",
    "calls": 514,
    "error": 8,
    "avg_duration_seconds": 0.445
  },
  {
    "tool": "code_explore",
    "calls": 490,
    "error": 0,
    "avg_duration_seconds": 0.326
  },
  {
    "tool": "call_capability",
    "calls": 479,
    "error": 17,
    "avg_duration_seconds": 0.695
  },
  {
    "tool": "run_test",
    "calls": 437,
    "error": 2,
    "avg_duration_seconds": 3.87
  },
  {
    "tool": "code_impact",
    "calls": 422,
    "error": 0,
    "avg_duration_seconds": 0.134
  },
  {
    "tool": "worktree_guard",
    "calls": 409,
    "error": 0,
    "avg_duration_seconds": 0.03
  },
  {
    "tool": "db_schema",
    "calls": 351,
    "error": 0,
    "avg_duration_seconds": 0.033
  }
]
```
