---
name: "工具台反馈-20260704-144632-codex-TaskQueue 与 KnowledgePipeline failed"
type: "reference"
tags: [mcp-feedback, dev-toolkit]
agent: "codex"
created: "2026-07-04T14:46:32.075634+00:00"
---

# MCP 使用反馈

## 任务

TaskQueue 与 KnowledgePipeline failed debt 最终收口复验、治理新残留任务和测试污染清理

## 顺畅度

- 评分：5/5
- 体感：整体顺畅；测试污染专用 audit/cleanup 工具非常有用，避免手写清理 SQL。

## 本次用到的工具

brief, plan_task, worktree_guard, routes, db_schema, code_explore, code_node, code_impact, probe, sql, release_gate, test_data_pollution_audit, test_data_pollution_cleanup, lint, run_test, finish_task, memory_write

## 卡点 / 不顺手的地方

release_gate 输出较长且有截断，定位样本仍需要额外 SQL 或 test_data_pollution_audit。

## 缺少的工具 / 能力

希望 release_gate 的 Test data pollution blocker 直接附 sample ids/name，减少二次查询。

## 升级建议

把 release_gate context 中的 test_data_pollution 增加 candidate_file_ids/sample_files，或提供 selector 参数只看 blockers 详情。

## 建议移除或合并的工具

无

## 其他备注

本轮未使用子代理继续扩展，主要做主会话验证与活系统收口；前置子代理审计已由上一阶段完成。

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
    "calls": 29,
    "error": 3,
    "avg_duration_seconds": 0.242
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
    "calls": 16,
    "error": 3,
    "avg_duration_seconds": 0.031
  },
  {
    "tool": "worktree_guard",
    "calls": 14,
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
    "calls": 11,
    "error": 0,
    "avg_duration_seconds": 1.504
  },
  {
    "tool": "capabilities",
    "calls": 6,
    "error": 0,
    "avg_duration_seconds": 0.001
  },
  {
    "tool": "code_explore",
    "calls": 6,
    "error": 0,
    "avg_duration_seconds": 0.373
  }
]
```
