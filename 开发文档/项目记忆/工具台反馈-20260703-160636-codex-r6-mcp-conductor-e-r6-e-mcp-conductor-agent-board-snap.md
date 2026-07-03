---
name: "工具台反馈-20260703-160636-codex-r6-mcp-conductor-e-R6-E MCP conductor: agent_board_snap"
type: "reference"
tags: [mcp-feedback, dev-toolkit]
agent: "codex-r6-mcp-conductor-e"
created: "2026-07-03T16:06:36.631469+00:00"
---

# MCP 使用反馈

## 任务

R6-E MCP conductor: agent_board_snapshot 多代理收工控制台增强

## 顺畅度

- 评分：4/5
- 体感：整体顺畅，CodeGraph + 工具台 workflow 很适合这类小范围 MCP 增强。

## 本次用到的工具

brief, plan_task, worktree_guard, code_explore, code_node, code_impact, lint, run_test, probe, tail_log, finish_task, memory_write, mcp_feedback

## 卡点 / 不顺手的地方

当前 MCP stdio server 不会热重载已导入模块，改完后直接调用同一 MCP 工具看不到新字段，需要用新 Python 进程或重启工具台验证。

## 缺少的工具 / 能力

缺一个 dev_toolkit 自身热重载/重启提示工具，或 finish_task 自动区分“本 agent 变更”和并行 worker 变更的简洁视图。

## 升级建议

让 agent_board_snapshot 的 conductor 输出下一步可继续接入 opencode job notifications/job_list，并在 stage_plan 支持按 agent/memory 关联过滤 pathspec。

## 建议移除或合并的工具

无

## 其他备注

本次避免触碰 dev_toolkit/release_gate.py 与 frontend/tests；外部 dirty 来自并行 worker。

## 当前工具热度快照

```json
[
  {
    "tool": "code_node",
    "calls": 1197,
    "error": 0,
    "avg_duration_seconds": 0.144
  },
  {
    "tool": "lint",
    "calls": 640,
    "error": 0,
    "avg_duration_seconds": 0.03
  },
  {
    "tool": "sql",
    "calls": 515,
    "error": 25,
    "avg_duration_seconds": 0.031
  },
  {
    "tool": "probe",
    "calls": 508,
    "error": 6,
    "avg_duration_seconds": 0.447
  },
  {
    "tool": "code_explore",
    "calls": 488,
    "error": 0,
    "avg_duration_seconds": 0.326
  },
  {
    "tool": "call_capability",
    "calls": 475,
    "error": 17,
    "avg_duration_seconds": 0.697
  },
  {
    "tool": "run_test",
    "calls": 432,
    "error": 2,
    "avg_duration_seconds": 3.83
  },
  {
    "tool": "code_impact",
    "calls": 422,
    "error": 0,
    "avg_duration_seconds": 0.134
  },
  {
    "tool": "worktree_guard",
    "calls": 408,
    "error": 0,
    "avg_duration_seconds": 0.03
  },
  {
    "tool": "db_schema",
    "calls": 351,
    "error": 0,
    "avg_duration_seconds": 0.033
  }
]
```
