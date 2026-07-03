---
name: "工具台反馈-20260703-062503-codex-memory-module-worker-20260703-r1-modules/memory 深度质量升级：修复参数 500、向量维度守"
type: "reference"
tags: [mcp-feedback, dev-toolkit]
agent: "codex-memory-module-worker-20260703-r1"
created: "2026-07-03T06:25:03.819600+00:00"
---

# MCP 使用反馈

## 任务

modules/memory 深度质量升级：修复参数 500、向量维度守卫、chunk/link orphan 清理和 experience_feedback SQL 类型错误，并完成活系统验证。

## 顺畅度

- 评分：4/5
- 体感：整体顺畅，codegraph/DB 反审计/能力探针组合很有效。

## 本次用到的工具

brief, plan_task, worktree_guard, code_explore, code_node, code_impact, routes, capabilities, db_reverse_audit, probe, call_capability, lint, run_test, finish_task, memory_write, agent_board_claim, agent_board_heartbeat

## 卡点 / 不顺手的地方

后端重启后短时间内 call_capability 偶发 All connection attempts failed，需手动等 health 稳定再重试；finish_task 对既有其他 worker dirty 无法区分本 agent 改动，边界结果会被全仓 dirty 污染。

## 缺少的工具 / 能力

希望有按 agent/时间范围过滤的 boundary guard，或传入 allowed_changed_files baseline 的边界检查。

## 升级建议

call_capability 可在后端刚重启时内置短重试；finish_task 可展示任务开始时 baseline 与当前 diff 的差集。

## 建议移除或合并的工具

无

## 其他备注

测试数据已清理；未提交。

## 当前工具热度快照

```json
[
  {
    "tool": "code_node",
    "calls": 613,
    "error": 0,
    "avg_duration_seconds": 0.145
  },
  {
    "tool": "lint",
    "calls": 447,
    "error": 0,
    "avg_duration_seconds": 0.019
  },
  {
    "tool": "code_explore",
    "calls": 293,
    "error": 0,
    "avg_duration_seconds": 0.325
  },
  {
    "tool": "sql",
    "calls": 272,
    "error": 13,
    "avg_duration_seconds": 0.031
  },
  {
    "tool": "worktree_guard",
    "calls": 229,
    "error": 0,
    "avg_duration_seconds": 0.031
  },
  {
    "tool": "run_test",
    "calls": 228,
    "error": 2,
    "avg_duration_seconds": 3.348
  },
  {
    "tool": "code_impact",
    "calls": 207,
    "error": 0,
    "avg_duration_seconds": 0.137
  },
  {
    "tool": "db_schema",
    "calls": 185,
    "error": 0,
    "avg_duration_seconds": 0.033
  },
  {
    "tool": "probe",
    "calls": 166,
    "error": 2,
    "avg_duration_seconds": 0.468
  },
  {
    "tool": "plan_task",
    "calls": 157,
    "error": 0,
    "avg_duration_seconds": 0.007
  }
]
```
