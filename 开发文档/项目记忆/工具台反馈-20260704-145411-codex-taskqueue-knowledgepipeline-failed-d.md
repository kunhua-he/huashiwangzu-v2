---
name: "工具台反馈-20260704-145411-codex-TaskQueue/KnowledgePipeline failed d"
type: "reference"
tags: [mcp-feedback, dev-toolkit]
agent: "codex"
created: "2026-07-04T14:54:11.450691+00:00"
---

# MCP 使用反馈

## 任务

TaskQueue/KnowledgePipeline failed debt 最终验收复核，追加治理 5138 并等待后台任务归零

## 顺畅度

- 评分：5/5
- 体感：工具整体顺畅，release_gate 和 audit 能清楚区分 deleted-source obsolete 与 blocker。

## 本次用到的工具

probe, release_gate, sql, test_data_pollution_audit, memory_write, mcp_feedback

## 卡点 / 不顺手的地方

活系统有后台 pipeline 继续生成任务和测试 marker 数据，需要多轮等待后再复验；release_gate 不直接给污染样本仍要用 audit 辅助。

## 缺少的工具 / 能力

希望有一个 wait_task_queue_idle 工具，可按 failed/pending/running/stale 条件轮询到稳定状态。

## 升级建议

给 test_data_pollution_audit 增加按时间戳/批次分组，便于判断是哪次 gate 或 e2e 产生。

## 建议移除或合并的工具

无

## 其他备注

最终无需改代码；只做活系统治理、复验和交付件同步。

## 当前工具热度快照

```json
[
  {
    "tool": "run_test",
    "calls": 42,
    "error": 0,
    "avg_duration_seconds": 2.686
  },
  {
    "tool": "probe",
    "calls": 41,
    "error": 3,
    "avg_duration_seconds": 0.247
  },
  {
    "tool": "code_node",
    "calls": 21,
    "error": 0,
    "avg_duration_seconds": 0.149
  },
  {
    "tool": "lint",
    "calls": 19,
    "error": 0,
    "avg_duration_seconds": 0.096
  },
  {
    "tool": "sql",
    "calls": 19,
    "error": 3,
    "avg_duration_seconds": 0.031
  },
  {
    "tool": "worktree_guard",
    "calls": 16,
    "error": 0,
    "avg_duration_seconds": 0.029
  },
  {
    "tool": "code_impact",
    "calls": 12,
    "error": 0,
    "avg_duration_seconds": 0.136
  },
  {
    "tool": "finish_task",
    "calls": 12,
    "error": 0,
    "avg_duration_seconds": 1.393
  },
  {
    "tool": "release_gate",
    "calls": 9,
    "error": 0,
    "avg_duration_seconds": 2.674
  },
  {
    "tool": "test_data_pollution_audit",
    "calls": 7,
    "error": 0,
    "avg_duration_seconds": 0.034
  }
]
```
