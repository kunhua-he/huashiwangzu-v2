---
name: "工具台反馈-20260704-143154-codex-TaskQueue 与 KnowledgePipeline failed"
type: "reference"
tags: [mcp-feedback, dev-toolkit]
agent: "codex"
created: "2026-07-04T14:31:54.925855+00:00"
---

# MCP 使用反馈

## 任务

TaskQueue 与 KnowledgePipeline failed debt deleted-source obsolete 治理收口

## 顺畅度

- 评分：4/5
- 体感：整体顺畅，probe/sql/release_gate 对活系统验收很直接。

## 本次用到的工具

brief, plan_task, worktree_guard, code_node, code_impact, routes, db_schema, probe, sql, lint, run_test, release_gate, tail_log, memory_write, mcp_feedback

## 卡点 / 不顺手的地方

worktree_guard 无法区分本轮与并行 agent 后续写入，工作区中途出现大量无关 dirty，需要人工隔离 staged hunks。

## 缺少的工具 / 能力

希望增加按时间/agent 自动生成 baseline 并支持 partial-stage 建议的收工工具。

## 升级建议

finish_task/worktree_guard 可支持传入 staged-only 视图，便于多代理同工作区时只验当前提交范围。

## 建议移除或合并的工具

无

## 其他备注

本次使用子代理做只读旁路审计，主会话独立验证后采纳了框架治理与 knowledge 专属能力同口径修复。

## 当前工具热度快照

```json
[
  {
    "tool": "run_test",
    "calls": 29,
    "error": 0,
    "avg_duration_seconds": 2.446
  },
  {
    "tool": "code_node",
    "calls": 15,
    "error": 0,
    "avg_duration_seconds": 0.147
  },
  {
    "tool": "probe",
    "calls": 15,
    "error": 3,
    "avg_duration_seconds": 0.225
  },
  {
    "tool": "lint",
    "calls": 13,
    "error": 0,
    "avg_duration_seconds": 0.064
  },
  {
    "tool": "code_impact",
    "calls": 11,
    "error": 0,
    "avg_duration_seconds": 0.134
  },
  {
    "tool": "worktree_guard",
    "calls": 10,
    "error": 0,
    "avg_duration_seconds": 0.03
  },
  {
    "tool": "finish_task",
    "calls": 8,
    "error": 0,
    "avg_duration_seconds": 0.375
  },
  {
    "tool": "capabilities",
    "calls": 6,
    "error": 0,
    "avg_duration_seconds": 0.001
  },
  {
    "tool": "tail_log",
    "calls": 4,
    "error": 0,
    "avg_duration_seconds": 0.006
  },
  {
    "tool": "tool_job_notifications",
    "calls": 3,
    "error": 0,
    "avg_duration_seconds": 0.0
  }
]
```
