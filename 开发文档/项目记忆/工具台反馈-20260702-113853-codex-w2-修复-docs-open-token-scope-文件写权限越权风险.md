---
name: "工具台反馈-20260702-113853-codex-w2-修复 docs-open token scope + 文件写权限越权风险"
type: "reference"
tags: [mcp-feedback, dev-toolkit]
agent: "codex-w2"
created: "2026-07-02T11:38:53.836403+00:00"
---

# MCP 使用反馈

## 任务

修复 docs-open token scope + 文件写权限越权风险并补回归测试

## 顺畅度

- 评分：4/5
- 体感：整体顺畅，CodeGraph 和 run_test 很好用。

## 本次用到的工具

brief, plan_task, worktree_guard, code_explore, code_node, code_impact, routes, lint, run_test, probe, tail_log, finish_task, memory_write

## 卡点 / 不顺手的地方

lint 工具一次只接受单文件路径，传多个路径会整体当成一个不存在路径；并行工作区很多其他改动时 worktree_guard 只能整体 false，需要人工解释本次 diff。

## 缺少的工具 / 能力

希望 lint 支持 path 数组；worktree_guard 支持 baseline/owned_paths，只校验本 agent 本次实际 diff。

## 升级建议

为 worktree_guard 增加 allowed_changed_subset 或 since-timestamp 模式，适合多 agent 并行维修。

## 建议移除或合并的工具

无

## 其他备注

本次未提交 commit。

## 当前工具热度快照

```json
[
  {
    "tool": "code_node",
    "calls": 115,
    "error": 0,
    "avg_duration_seconds": 0.139
  },
  {
    "tool": "lint",
    "calls": 77,
    "error": 0,
    "avg_duration_seconds": 0.016
  },
  {
    "tool": "code_explore",
    "calls": 57,
    "error": 0,
    "avg_duration_seconds": 0.304
  },
  {
    "tool": "sql",
    "calls": 50,
    "error": 0,
    "avg_duration_seconds": 0.033
  },
  {
    "tool": "worktree_guard",
    "calls": 37,
    "error": 0,
    "avg_duration_seconds": 0.031
  },
  {
    "tool": "code_impact",
    "calls": 31,
    "error": 0,
    "avg_duration_seconds": 0.136
  },
  {
    "tool": "db_schema",
    "calls": 28,
    "error": 0,
    "avg_duration_seconds": 0.033
  },
  {
    "tool": "plan_task",
    "calls": 26,
    "error": 0,
    "avg_duration_seconds": 0.006
  },
  {
    "tool": "routes",
    "calls": 26,
    "error": 0,
    "avg_duration_seconds": 0.047
  },
  {
    "tool": "probe",
    "calls": 25,
    "error": 0,
    "avg_duration_seconds": 0.582
  }
]
```
