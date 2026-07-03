---
name: "工具台反馈-20260702-181053-knowledge-chain-probe-r7-审计 knowledge ingest->parse->chunks->"
type: "reference"
tags: [mcp-feedback, dev-toolkit]
agent: "knowledge-chain-probe-r7"
created: "2026-07-02T18:10:53.140587+00:00"
---

# MCP 使用反馈

## 任务

审计 knowledge ingest->parse->chunks->search->governance 主链路，模块内补 pipeline 诊断收尾兜底并补测试。

## 顺畅度

- 评分：4/5
- 体感：整体顺畅，brief/plan_task/codegraph/probe/sql 能快速把代码链路和真实 DB 状态对上。

## 本次用到的工具

brief, plan_task, worktree_guard, code_explore, code_node, code_impact, routes, capabilities, db_schema, sql, probe, call_capability, lint, run_test, tail_log, finish_task, memory_write

## 卡点 / 不顺手的地方

finish_task 的默认边界只允许 modules/knowledge，无法表达本任务用户允许 backend/tests 和 项目记忆；会把既有外部脏文件混入本次边界失败，需要人工解释。

## 缺少的工具 / 能力

希望有按本 agent 本次触碰文件过滤的 dirty/boundary 工具，区分 before/after 改动。

## 升级建议

pipeline/codemap 审计场景可加一个“按 document_id 聚合 queue + kb_pipeline_runs + stage_runs + doc status”的只读工具，避免手写多条 SQL。

## 建议移除或合并的工具

无

## 其他备注

本次没有批量修改真实 DB；只报告历史 failed 队列和 stale running 诊断债。

## 当前工具热度快照

```json
[
  {
    "tool": "code_node",
    "calls": 441,
    "error": 0,
    "avg_duration_seconds": 0.145
  },
  {
    "tool": "lint",
    "calls": 275,
    "error": 0,
    "avg_duration_seconds": 0.016
  },
  {
    "tool": "sql",
    "calls": 238,
    "error": 10,
    "avg_duration_seconds": 0.031
  },
  {
    "tool": "code_explore",
    "calls": 224,
    "error": 0,
    "avg_duration_seconds": 0.321
  },
  {
    "tool": "db_schema",
    "calls": 154,
    "error": 0,
    "avg_duration_seconds": 0.033
  },
  {
    "tool": "worktree_guard",
    "calls": 148,
    "error": 0,
    "avg_duration_seconds": 0.031
  },
  {
    "tool": "run_test",
    "calls": 140,
    "error": 0,
    "avg_duration_seconds": 2.758
  },
  {
    "tool": "code_impact",
    "calls": 136,
    "error": 0,
    "avg_duration_seconds": 0.139
  },
  {
    "tool": "probe",
    "calls": 119,
    "error": 0,
    "avg_duration_seconds": 0.493
  },
  {
    "tool": "plan_task",
    "calls": 101,
    "error": 0,
    "avg_duration_seconds": 0.007
  }
]
```
