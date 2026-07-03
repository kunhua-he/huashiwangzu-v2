---
name: "工具台反馈-20260703-155150-codex-conductor-r5-R5 第一阶段主会话集成验收：整合五泳道 knowledge/dev_t"
type: "reference"
tags: [mcp-feedback, dev-toolkit]
agent: "codex-conductor-r5"
created: "2026-07-03T15:51:50.792404+00:00"
---

# MCP 使用反馈

## 任务

R5 第一阶段主会话集成验收：整合五泳道 knowledge/dev_toolkit 修复，执行小批生产治理并通过 release gate

## 顺畅度

- 评分：4/5
- 体感：整体顺畅，尤其 selector/max_bytes 生效后治理类大响应可控很多。

## 本次用到的工具

brief, plan_task, worktree_guard, code_explore, code_node, code_impact, lint, run_test, probe, call_capability, routes, capabilities, sql, tail_log, finish_task, memory_write

## 卡点 / 不顺手的地方

read_thread 能恢复旧线程，但旧 systemError 的 process_manager 残留仍需要人工判断；release_gate 没有在当前工具列表中直接暴露，只能用 shell 跑。

## 缺少的工具 / 能力

希望提供 release_gate 作为直接 MCP callable，并提供已归档历史队列的小批 apply 计划生成工具。

## 升级建议

process_manager 可以自动清理已不存在 PID 的卡住命令记录；call_capability/probe 的 selector warning 可以提示候选路径。

## 建议移除或合并的工具

无

## 其他备注

本轮用新 response trim 验证了自身价值：classify_pipeline_debt 可只取 summary/problem_queue，避免刷屏。

## 当前工具热度快照

```json
[
  {
    "tool": "code_node",
    "calls": 1145,
    "error": 0,
    "avg_duration_seconds": 0.145
  },
  {
    "tool": "lint",
    "calls": 629,
    "error": 0,
    "avg_duration_seconds": 0.029
  },
  {
    "tool": "sql",
    "calls": 508,
    "error": 25,
    "avg_duration_seconds": 0.031
  },
  {
    "tool": "probe",
    "calls": 490,
    "error": 6,
    "avg_duration_seconds": 0.447
  },
  {
    "tool": "code_explore",
    "calls": 472,
    "error": 0,
    "avg_duration_seconds": 0.327
  },
  {
    "tool": "call_capability",
    "calls": 466,
    "error": 17,
    "avg_duration_seconds": 0.703
  },
  {
    "tool": "run_test",
    "calls": 419,
    "error": 2,
    "avg_duration_seconds": 3.925
  },
  {
    "tool": "code_impact",
    "calls": 405,
    "error": 0,
    "avg_duration_seconds": 0.135
  },
  {
    "tool": "worktree_guard",
    "calls": 395,
    "error": 0,
    "avg_duration_seconds": 0.031
  },
  {
    "tool": "db_schema",
    "calls": 340,
    "error": 0,
    "avg_duration_seconds": 0.033
  }
]
```
