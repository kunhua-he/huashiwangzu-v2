---
name: "工具台反馈-20260703-184935-codex-test-acceleration-conductor-执行测试加速专项：release gate 测试分层、matrix 定向"
type: "reference"
tags: [mcp-feedback, dev-toolkit]
agent: "codex-test-acceleration-conductor"
created: "2026-07-03T18:49:35.650795+00:00"
---

# MCP 使用反馈

## 任务

执行测试加速专项：release gate 测试分层、matrix 定向/并发、UI 截图开关、smoke/release gate token 和队列等待优化、测试分层文档化。

## 顺畅度

- 评分：4/5
- 体感：整体顺畅，brief/plan/worktree_guard/codegraph/finish_task 对多代理并行收束很有帮助。

## 本次用到的工具

brief, plan_task, worktree_guard, code_explore, code_node, code_impact, routes, capabilities, db_schema, lint, finish_task, memory_write, mcp_feedback

## 卡点 / 不顺手的地方

finish_task 的 baseline_count 为空时会把开工前已有项目记忆也列为 new_since_baseline；多代理并行时需要手动解释哪些是前序留痕。

## 缺少的工具 / 能力

希望 tool_job 或 finish_task 能自动记录 wall time 表格，减少手工整理耗时对比。

## 升级建议

为 release/smoke 这类会互相刷新登录态的工具增加统一共享 token client 或自动 401 retry 模板。

## 建议移除或合并的工具

无

## 其他备注

本次发现并修复 release_gate 与 smoke 并发登录导致 401 后误报 audit missing summary 的问题。

## 当前工具热度快照

```json
[
  {
    "tool": "code_node",
    "calls": 1312,
    "error": 0,
    "avg_duration_seconds": 0.144
  },
  {
    "tool": "lint",
    "calls": 660,
    "error": 0,
    "avg_duration_seconds": 0.031
  },
  {
    "tool": "probe",
    "calls": 575,
    "error": 8,
    "avg_duration_seconds": 0.448
  },
  {
    "tool": "code_explore",
    "calls": 566,
    "error": 0,
    "avg_duration_seconds": 0.326
  },
  {
    "tool": "sql",
    "calls": 566,
    "error": 35,
    "avg_duration_seconds": 0.031
  },
  {
    "tool": "call_capability",
    "calls": 499,
    "error": 17,
    "avg_duration_seconds": 0.681
  },
  {
    "tool": "worktree_guard",
    "calls": 475,
    "error": 0,
    "avg_duration_seconds": 0.03
  },
  {
    "tool": "run_test",
    "calls": 469,
    "error": 3,
    "avg_duration_seconds": 4.428
  },
  {
    "tool": "code_impact",
    "calls": 456,
    "error": 0,
    "avg_duration_seconds": 0.134
  },
  {
    "tool": "db_schema",
    "calls": 371,
    "error": 0,
    "avg_duration_seconds": 0.033
  }
]
```
