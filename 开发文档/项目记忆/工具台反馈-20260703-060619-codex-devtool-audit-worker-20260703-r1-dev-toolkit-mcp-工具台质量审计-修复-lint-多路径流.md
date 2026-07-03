---
name: "工具台反馈-20260703-060619-codex-devtool-audit-worker-20260703-r1-dev_toolkit MCP 工具台质量审计：修复 lint 多路径流"
type: "reference"
tags: [mcp-feedback, dev-toolkit]
agent: "codex-devtool-audit-worker-20260703-r1"
created: "2026-07-03T06:06:19.988446+00:00"
---

# MCP 使用反馈

## 任务

dev_toolkit MCP 工具台质量审计：修复 lint 多路径流程摩擦，并强化 agent_board heartbeat 未 claim 提示。

## 顺畅度

- 评分：4/5
- 体感：整体顺畅，brief/plan/worktree_guard/codegraph/finish_task 串起来很省心，agent_board 落盘可验证。

## 本次用到的工具

brief, plan_task, worktree_guard, code_explore, code_node, code_impact, mcp_self_check, mcp_feedback_summary, agent_board_claim, agent_board_heartbeat, agent_board_snapshot, finish_task, memory_write, mcp_feedback

## 卡点 / 不顺手的地方

agent_board_heartbeat 在任务未 claim 时只报 task not found，开局容易踩；已在代码中补 hint/claim_example。finish_task 不能传 allowed_prefixes，在共享脏工作区里无法表达“全局任务但只允许 dev_toolkit”。

## 缺少的工具 / 能力

希望 finish_task 增加 allowed_prefixes/forbidden_prefixes 参数，并在报告中区分本 agent touched files 与全仓 dirty。

## 升级建议

给 memory_write/mcp_feedback 增加跨进程文件锁，避免多个 MCP 进程同时写项目记忆索引或 embedding cache 时互相覆盖；给 mcp_self_check 增加 disk-vs-loaded module version 提示。

## 建议移除或合并的工具

无

## 其他备注

本轮直接修了 lint 多路径和 heartbeat 恢复提示；队列/agent_board 已有文件锁与 corrupt recovery 测试，未发现需要越界修的问题。

## 当前工具热度快照

```json
[
  {
    "tool": "code_node",
    "calls": 566,
    "error": 0,
    "avg_duration_seconds": 0.145
  },
  {
    "tool": "lint",
    "calls": 419,
    "error": 0,
    "avg_duration_seconds": 0.017
  },
  {
    "tool": "code_explore",
    "calls": 284,
    "error": 0,
    "avg_duration_seconds": 0.324
  },
  {
    "tool": "sql",
    "calls": 271,
    "error": 13,
    "avg_duration_seconds": 0.031
  },
  {
    "tool": "worktree_guard",
    "calls": 218,
    "error": 0,
    "avg_duration_seconds": 0.031
  },
  {
    "tool": "run_test",
    "calls": 210,
    "error": 2,
    "avg_duration_seconds": 3.222
  },
  {
    "tool": "code_impact",
    "calls": 195,
    "error": 0,
    "avg_duration_seconds": 0.138
  },
  {
    "tool": "db_schema",
    "calls": 174,
    "error": 0,
    "avg_duration_seconds": 0.033
  },
  {
    "tool": "plan_task",
    "calls": 153,
    "error": 0,
    "avg_duration_seconds": 0.007
  },
  {
    "tool": "probe",
    "calls": 149,
    "error": 0,
    "avg_duration_seconds": 0.455
  }
]
```
