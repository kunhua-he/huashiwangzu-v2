---
name: "工具台反馈-20260705-045805-codex-TaskQueue 与 KnowledgePipeline failed"
type: "reference"
tags: [mcp-feedback, dev-toolkit]
agent: "codex"
created: "2026-07-05T04:58:05.091134+00:00"
---

# MCP 使用反馈

## 任务

TaskQueue 与 KnowledgePipeline failed 债务治理最终验收、5706 追加归档、release_gate 拆分和测试污染清理

## 顺畅度

- 评分：4/5
- 体感：整体顺畅；probe/governance/test pollution 工具对活系统收口很有用。

## 本次用到的工具

brief, plan_task, worktree_guard, code_impact, routes, db_schema, probe, sql, test_data_pollution_audit, test_data_pollution_cleanup, call_capability, lint, run_test, release_gate, memory_write, mcp_feedback

## 卡点 / 不顺手的地方

release_gate(preflight) 期间仍可能叠加已有 smoke/e2e 数据，导致 gate 后需要再次 test_data_pollution_cleanup；需要注意先看活跃任务和污染。

## 缺少的工具 / 能力

无

## 升级建议

建议 release_gate 可选只读/不产出测试数据模式，或在输出里区分本次 gate 前已有污染与 gate 期间新增污染。

## 建议移除或合并的工具

无

## 其他备注

本轮用子代理只读审计五件套，主会话复验后修正 stale HEAD、证据缺失和 release_gate 行数风险。

## 当前工具热度快照

```json
[
  {
    "tool": "probe",
    "calls": 54,
    "error": 3,
    "avg_duration_seconds": 0.256
  },
  {
    "tool": "run_test",
    "calls": 51,
    "error": 0,
    "avg_duration_seconds": 2.735
  },
  {
    "tool": "lint",
    "calls": 26,
    "error": 0,
    "avg_duration_seconds": 0.091
  },
  {
    "tool": "sql",
    "calls": 24,
    "error": 3,
    "avg_duration_seconds": 0.03
  },
  {
    "tool": "code_node",
    "calls": 21,
    "error": 0,
    "avg_duration_seconds": 0.149
  },
  {
    "tool": "worktree_guard",
    "calls": 21,
    "error": 0,
    "avg_duration_seconds": 0.029
  },
  {
    "tool": "release_gate",
    "calls": 14,
    "error": 0,
    "avg_duration_seconds": 25.068
  },
  {
    "tool": "code_impact",
    "calls": 13,
    "error": 0,
    "avg_duration_seconds": 0.137
  },
  {
    "tool": "finish_task",
    "calls": 13,
    "error": 0,
    "avg_duration_seconds": 1.29
  },
  {
    "tool": "test_data_pollution_audit",
    "calls": 13,
    "error": 0,
    "avg_duration_seconds": 0.033
  }
]
```
