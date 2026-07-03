---
name: "工具台反馈-20260703-062304-codex-terminal-tools-worker-20260703-r1-terminal-tools 模块边界、输出上限、临时目录清理和 REA"
type: "reference"
tags: [mcp-feedback, dev-toolkit]
agent: "codex-terminal-tools-worker-20260703-r1"
created: "2026-07-03T06:23:04.668815+00:00"
---

# MCP 使用反馈

## 任务

terminal-tools 模块边界、输出上限、临时目录清理和 README 验收质量升级

## 顺畅度

- 评分：4/5
- 体感：整体顺畅，brief/plan/worktree_guard/codegraph/lint/finish_task 串起来能形成完整闭环。

## 本次用到的工具

brief, plan_task, worktree_guard, capabilities, routes, db_schema, code_explore, code_node, code_impact, lint, probe, call_capability, tail_log, finish_task, memory_write, agent_board_claim, agent_board_heartbeat

## 卡点 / 不顺手的地方

finish_task/worktree_guard 在多人同仓大量 dirty 时只能给全仓失败，不能区分本 agent 本次改动与既有外部改动；活系统未启动时 probe/call_capability 只返回连接失败，缺少一键诊断建议。

## 缺少的工具 / 能力

希望有按 git diff pathspec 生成模块边界结论的工具，能输出“本模块 diff 通过、全仓有他人 dirty”两层状态。

## 升级建议

finish_task 可支持 expected_changed_prefixes 与 known_external_dirty=ignore 模式，并保留全仓 dirty 警告但不把本任务标红。probe 连接失败时可自动附带端口监听检查结果。

## 建议移除或合并的工具

无

## 其他备注

本次没有重启后端，避免扰动其他 worker；用直接模块回归补足新逻辑验证。

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
    "calls": 292,
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
    "tool": "run_test",
    "calls": 228,
    "error": 2,
    "avg_duration_seconds": 3.348
  },
  {
    "tool": "worktree_guard",
    "calls": 227,
    "error": 0,
    "avg_duration_seconds": 0.031
  },
  {
    "tool": "code_impact",
    "calls": 207,
    "error": 0,
    "avg_duration_seconds": 0.137
  },
  {
    "tool": "db_schema",
    "calls": 184,
    "error": 0,
    "avg_duration_seconds": 0.033
  },
  {
    "tool": "probe",
    "calls": 164,
    "error": 2,
    "avg_duration_seconds": 0.47
  },
  {
    "tool": "plan_task",
    "calls": 157,
    "error": 0,
    "avg_duration_seconds": 0.007
  }
]
```
