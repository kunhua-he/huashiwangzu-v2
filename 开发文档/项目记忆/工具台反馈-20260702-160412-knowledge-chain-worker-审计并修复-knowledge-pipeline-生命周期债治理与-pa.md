---
name: "工具台反馈-20260702-160412-knowledge-chain-worker-审计并修复 knowledge pipeline 生命周期债治理与 pa"
type: "reference"
tags: [mcp-feedback, dev-toolkit]
agent: "knowledge-chain-worker"
created: "2026-07-02T16:04:12.208545+00:00"
---

# MCP 使用反馈

## 任务

审计并修复 knowledge pipeline 生命周期债治理与 parser 空内容软失败链路

## 顺畅度

- 评分：4/5
- 体感：整体顺畅，CodeGraph + 工具台足够定位知识库链路和验证边界。

## 本次用到的工具

brief, plan_task, worktree_guard, code_explore, code_node, code_impact, routes, capabilities, db_schema, sql, probe, tail_log, lint, run_test, finish_task, memory_write

## 卡点 / 不顺手的地方

finish_task 的 test_targets 对 backend cwd 测试与 repo 根模块测试混合目标归一化不准，导致已手动通过的组合在 finish_task 里显示 no tests ran；工作区大量其他 agent dirty 也让边界检查只能作为提示而非本轮通过/失败依据。

## 缺少的工具 / 能力

希望 worktree_guard/finish_task 支持传入 baseline 或只检查本轮触碰文件；希望 run_test 支持多个 target 分别按各自 cwd 运行后汇总。

## 升级建议

finish_task 可接受 verification_summary_only 或 external_test_results，避免重复执行不适合混合 cwd 的测试目标；worktree_guard 可输出和开工初始状态的增量 diff。

## 建议移除或合并的工具

无

## 其他备注

常驻后端未重启，因为共享工作区有大量 backend/app 未提交改动，重启会把非本任务代码一起载入。

## 当前工具热度快照

```json
[
  {
    "tool": "code_node",
    "calls": 287,
    "error": 0,
    "avg_duration_seconds": 0.145
  },
  {
    "tool": "lint",
    "calls": 229,
    "error": 0,
    "avg_duration_seconds": 0.017
  },
  {
    "tool": "sql",
    "calls": 159,
    "error": 7,
    "avg_duration_seconds": 0.03
  },
  {
    "tool": "code_explore",
    "calls": 149,
    "error": 0,
    "avg_duration_seconds": 0.309
  },
  {
    "tool": "code_impact",
    "calls": 94,
    "error": 0,
    "avg_duration_seconds": 0.139
  },
  {
    "tool": "worktree_guard",
    "calls": 90,
    "error": 0,
    "avg_duration_seconds": 0.03
  },
  {
    "tool": "run_test",
    "calls": 78,
    "error": 0,
    "avg_duration_seconds": 2.978
  },
  {
    "tool": "db_schema",
    "calls": 76,
    "error": 0,
    "avg_duration_seconds": 0.034
  },
  {
    "tool": "probe",
    "calls": 64,
    "error": 0,
    "avg_duration_seconds": 0.494
  },
  {
    "tool": "plan_task",
    "calls": 63,
    "error": 0,
    "avg_duration_seconds": 0.007
  }
]
```
