---
name: "工具台反馈-20260702-144236-codex-scheduler-false-green-worker-修复 scheduler 能力失败语义假绿，并补 focused tes"
type: "reference"
tags: [mcp-feedback, dev-toolkit]
agent: "codex-scheduler-false-green-worker"
created: "2026-07-02T14:42:36.231468+00:00"
---

# MCP 使用反馈

## 任务

修复 scheduler 能力失败语义假绿，并补 focused tests。

## 顺畅度

- 评分：4/5
- 体感：整体顺畅，brief/plan_task/codegraph/lint/test 能覆盖本次小修。

## 本次用到的工具

brief, plan_task, worktree_guard, code_explore, code_node, code_impact, routes, capabilities, db_schema, lint, run_test, probe, tail_log, finish_task, memory_write

## 卡点 / 不顺手的地方

run_test 对 repo 根路径 modules/scheduler/sandbox/test_module.py 归一化到 backend cwd 后找不到文件，需要手动在仓库根运行 pytest；worktree_guard 在多人 dirty 场景会把既有其他会话改动一起报红，需要人工区分本节点 diff。

## 缺少的工具 / 能力

希望 finish_task/worktree_guard 支持 allowed_prefixes 参数，以便模块任务允许 backend/tests 的专项测试文件。

## 升级建议

run_test 可以识别 modules/*/sandbox/test_module.py 并自动从 repo root 执行，避免路径假失败。

## 建议移除或合并的工具

无

## 其他备注

本节点未触碰 dev_toolkit、agent、knowledge、content、event_bus。

## 当前工具热度快照

```json
[
  {
    "tool": "code_node",
    "calls": 191,
    "error": 0,
    "avg_duration_seconds": 0.139
  },
  {
    "tool": "lint",
    "calls": 182,
    "error": 0,
    "avg_duration_seconds": 0.016
  },
  {
    "tool": "sql",
    "calls": 139,
    "error": 5,
    "avg_duration_seconds": 0.031
  },
  {
    "tool": "code_explore",
    "calls": 117,
    "error": 0,
    "avg_duration_seconds": 0.301
  },
  {
    "tool": "worktree_guard",
    "calls": 62,
    "error": 0,
    "avg_duration_seconds": 0.029
  },
  {
    "tool": "code_impact",
    "calls": 53,
    "error": 0,
    "avg_duration_seconds": 0.132
  },
  {
    "tool": "db_schema",
    "calls": 51,
    "error": 0,
    "avg_duration_seconds": 0.033
  },
  {
    "tool": "probe",
    "calls": 51,
    "error": 0,
    "avg_duration_seconds": 0.486
  },
  {
    "tool": "run_test",
    "calls": 45,
    "error": 0,
    "avg_duration_seconds": 3.89
  },
  {
    "tool": "plan_task",
    "calls": 44,
    "error": 0,
    "avg_duration_seconds": 0.009
  }
]
```
