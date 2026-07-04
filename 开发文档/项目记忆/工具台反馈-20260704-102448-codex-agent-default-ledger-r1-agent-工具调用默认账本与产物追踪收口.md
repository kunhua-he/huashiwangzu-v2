---
name: "工具台反馈-20260704-102448-codex-agent-default-ledger-r1-Agent 工具调用默认账本与产物追踪收口"
type: "reference"
tags: [mcp-feedback, dev-toolkit]
agent: "codex-agent-default-ledger-r1"
created: "2026-07-04T10:24:48.008994+00:00"
---

# MCP 使用反馈

## 任务

Agent 工具调用默认账本与产物追踪收口

## 顺畅度

- 评分：4/5
- 体感：整体顺畅，brief/plan_task/codegraph/finish_task 能把任务边界和验证口径串起来。

## 本次用到的工具

brief, plan_task, worktree_guard, code_explore, code_node, code_impact, routes, capabilities, db_schema, call_capability, probe, tail_log, finish_task, memory_write, mcp_feedback

## 卡点 / 不顺手的地方

finish_task 对并发产生的 outside dirty 无法区分“本轮外部代理改动”和主会话改动，只能在 risk_note 里解释。

## 缺少的工具 / 能力

希望有一个按本轮 touched files 或 agent ownership 生成边界报告的工具，避免并行任务时模块边界误报。

## 升级建议

finish_task 可支持传入 explicit_touched_paths，并将 boundary 分成 actual_touched 与 workspace_dirty 两层。

## 建议移除或合并的工具

无

## 其他备注

本轮使用 3 个只读子代理加速定位调用链、账本模型和前端展示面；子代理均已关闭。

## 当前工具热度快照

```json
[
  {
    "tool": "call_capability",
    "calls": 78,
    "error": 5,
    "avg_duration_seconds": 0.293
  },
  {
    "tool": "code_node",
    "calls": 75,
    "error": 0,
    "avg_duration_seconds": 0.142
  },
  {
    "tool": "code_explore",
    "calls": 51,
    "error": 0,
    "avg_duration_seconds": 0.353
  },
  {
    "tool": "worktree_guard",
    "calls": 37,
    "error": 0,
    "avg_duration_seconds": 0.029
  },
  {
    "tool": "run_test",
    "calls": 36,
    "error": 0,
    "avg_duration_seconds": 4.923
  },
  {
    "tool": "sql",
    "calls": 35,
    "error": 3,
    "avg_duration_seconds": 0.031
  },
  {
    "tool": "brief",
    "calls": 29,
    "error": 0,
    "avg_duration_seconds": 0.744
  },
  {
    "tool": "code_impact",
    "calls": 29,
    "error": 0,
    "avg_duration_seconds": 0.13
  },
  {
    "tool": "plan_task",
    "calls": 27,
    "error": 0,
    "avg_duration_seconds": 0.006
  },
  {
    "tool": "probe",
    "calls": 26,
    "error": 0,
    "avg_duration_seconds": 0.58
  }
]
```
