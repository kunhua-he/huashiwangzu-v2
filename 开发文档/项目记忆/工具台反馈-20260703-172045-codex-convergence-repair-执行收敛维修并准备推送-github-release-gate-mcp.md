---
name: "工具台反馈-20260703-172045-codex-convergence-repair-执行收敛维修并准备推送 GitHub：release gate/MCP "
type: "reference"
tags: [mcp-feedback, dev-toolkit]
agent: "codex-convergence-repair"
created: "2026-07-03T17:20:45.115949+00:00"
---

# MCP 使用反馈

## 任务

执行收敛维修并准备推送 GitHub：release gate/MCP fail-closed+preflight，reset_runtime_data 加固，backups ignore，UI delete/recycle restore id 修复，agent_board stale 接管。

## 顺畅度

- 评分：5/5
- 体感：整体顺畅，工具台能支撑主控和子代理并行收敛。

## 本次用到的工具

brief, plan_task, worktree_guard, code_explore, code_node, code_impact, agent_board_snapshot, agent_board_claim, agent_board_heartbeat, finish_task, probe, memory_write, mcp_feedback

## 卡点 / 不顺手的地方

release_gate MCP 工具此前只有 skip_ui 且默认完整慢跑，容易超过外层等待；本轮已补 mode=preflight/full。

## 缺少的工具 / 能力

无

## 升级建议

release_gate MCP schema 变更后，可考虑工具台文档增加 preflight/full 使用示例；worktree_guard 可继续增强 tracked/untracked 分类展示。

## 建议移除或合并的工具

无

## 其他备注

本轮未创建 PR；按用户要求 commit 并 push 当前分支。

## 当前工具热度快照

```json
[
  {
    "tool": "code_node",
    "calls": 1228,
    "error": 0,
    "avg_duration_seconds": 0.144
  },
  {
    "tool": "lint",
    "calls": 649,
    "error": 0,
    "avg_duration_seconds": 0.031
  },
  {
    "tool": "probe",
    "calls": 545,
    "error": 8,
    "avg_duration_seconds": 0.451
  },
  {
    "tool": "sql",
    "calls": 535,
    "error": 30,
    "avg_duration_seconds": 0.03
  },
  {
    "tool": "code_explore",
    "calls": 515,
    "error": 0,
    "avg_duration_seconds": 0.326
  },
  {
    "tool": "call_capability",
    "calls": 495,
    "error": 17,
    "avg_duration_seconds": 0.684
  },
  {
    "tool": "run_test",
    "calls": 448,
    "error": 2,
    "avg_duration_seconds": 4.543
  },
  {
    "tool": "code_impact",
    "calls": 438,
    "error": 0,
    "avg_duration_seconds": 0.134
  },
  {
    "tool": "worktree_guard",
    "calls": 428,
    "error": 0,
    "avg_duration_seconds": 0.03
  },
  {
    "tool": "db_schema",
    "calls": 362,
    "error": 0,
    "avg_duration_seconds": 0.033
  }
]
```
