---
name: "工具台反馈-20260702-160132-fake-success-audit-worker-专项审计 fake-success/吞异常链路，修复 image-gen"
type: "reference"
tags: [mcp-feedback, dev-toolkit]
agent: "fake-success-audit-worker"
created: "2026-07-02T16:01:32.740637+00:00"
---

# MCP 使用反馈

## 任务

专项审计 fake-success/吞异常链路，修复 image-gen 空产物与历史查询异常假成功，补 focused regression。

## 顺畅度

- 评分：4/5
- 体感：整体顺畅，brief/plan/worktree_guard/code tools/lint/run_test/probe/finish 串起来能覆盖完整审计流程。

## 本次用到的工具

brief, plan_task, worktree_guard, code_explore, code_node, code_impact, routes, capabilities, db_schema, lint, run_test, probe, tail_log, finish_task, memory_write, mcp_feedback

## 卡点 / 不顺手的地方

当前会话没有直接暴露项目工具台命名工具，需要通过 stdio MCP 客户端脚本调用；另外 worktree_guard 在多人脏工作区下信息量很大，需要人工区分归因。

## 缺少的工具 / 能力

希望有一个按当前 agent 声明 changed_files 的收尾归因工具，能在全仓脏改动很多时生成“本次实际改动”小清单。

## 升级建议

worktree_guard/finish_task 可以增加 since-start 快照或 agent-local touched files 字段，减少并行 worker 现场的噪声。

## 建议移除或合并的工具

无

## 其他备注

无

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
    "calls": 215,
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
    "calls": 88,
    "error": 0,
    "avg_duration_seconds": 0.03
  },
  {
    "tool": "db_schema",
    "calls": 76,
    "error": 0,
    "avg_duration_seconds": 0.034
  },
  {
    "tool": "run_test",
    "calls": 75,
    "error": 0,
    "avg_duration_seconds": 3.05
  },
  {
    "tool": "plan_task",
    "calls": 62,
    "error": 0,
    "avg_duration_seconds": 0.007
  },
  {
    "tool": "probe",
    "calls": 62,
    "error": 0,
    "avg_duration_seconds": 0.491
  }
]
```
