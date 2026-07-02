---
name: "工具台反馈-20260702-112119-codex-只读调研 framework_system_task_queues 历史"
type: "reference"
tags: [mcp-feedback, dev-toolkit]
agent: "codex"
created: "2026-07-02T11:21:19.611659+00:00"
---

# MCP 使用反馈

## 任务

只读调研 framework_system_task_queues 历史 failed 队列债务，定位主要失败来源和治理建议。

## 顺畅度

- 评分：4/5
- 体感：整体顺畅，brief/plan_task/sql/probe/code_node 组合足够完成队列债务调查。

## 本次用到的工具

brief, plan_task, worktree_guard, db_schema, probe, routes, sql, code_explore, code_node, tail_log, finish_task, memory_write

## 卡点 / 不顺手的地方

codegraph 没索引到新文件 source_file_state.py/file_lifecycle_service.py，需要回退 sed 实读；SQL 输出列名统一成 col0/col1，做报告时需要手工映射字段。

## 缺少的工具 / 能力

建议增加 task_queue_debt_report 工具：内置 failed 分类、JSON 参数解析、关联业务表、可选 dry-run 治理建议，不直接写库。

## 升级建议

sql 工具可保留原始列名；worker audit 的 historical_debt_total 当前是 limit 500 的样本数，建议字段名改为 historical_debt_sample_count，并另给 total count，避免误解。

## 建议移除或合并的工具

无。

## 其他备注

本次没有执行 reconcile/清理/重试，只做只读证据和项目记忆。

## 当前工具热度快照

```json
[
  {
    "tool": "code_node",
    "calls": 83,
    "error": 0,
    "avg_duration_seconds": 0.138
  },
  {
    "tool": "code_explore",
    "calls": 52,
    "error": 0,
    "avg_duration_seconds": 0.303
  },
  {
    "tool": "lint",
    "calls": 39,
    "error": 0,
    "avg_duration_seconds": 0.017
  },
  {
    "tool": "sql",
    "calls": 35,
    "error": 0,
    "avg_duration_seconds": 0.032
  },
  {
    "tool": "worktree_guard",
    "calls": 32,
    "error": 0,
    "avg_duration_seconds": 0.032
  },
  {
    "tool": "probe",
    "calls": 24,
    "error": 0,
    "avg_duration_seconds": 0.593
  },
  {
    "tool": "db_schema",
    "calls": 23,
    "error": 0,
    "avg_duration_seconds": 0.033
  },
  {
    "tool": "plan_task",
    "calls": 22,
    "error": 0,
    "avg_duration_seconds": 0.003
  },
  {
    "tool": "routes",
    "calls": 21,
    "error": 0,
    "avg_duration_seconds": 0.052
  },
  {
    "tool": "code_impact",
    "calls": 20,
    "error": 0,
    "avg_duration_seconds": 0.134
  }
]
```
