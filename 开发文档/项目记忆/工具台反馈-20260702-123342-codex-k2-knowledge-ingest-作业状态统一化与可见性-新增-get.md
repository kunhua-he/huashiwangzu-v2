---
name: "工具台反馈-20260702-123342-codex-k2-knowledge:ingest 作业状态统一化与可见性，新增 get_"
type: "reference"
tags: [mcp-feedback, dev-toolkit]
agent: "codex-k2"
created: "2026-07-02T12:33:42.477480+00:00"
---

# MCP 使用反馈

## 任务

knowledge:ingest 作业状态统一化与可见性，新增 get_ingest_status 能力和 HTTP 状态入口

## 顺畅度

- 评分：4/5
- 体感：整体顺畅，CodeGraph 和工具台能快速定位 ingest/register/task 队列链路。

## 本次用到的工具

brief, plan_task, worktree_guard, capabilities, code_explore, code_node, code_impact, routes, db_schema, lint, run_test, probe, tail_log, finish_task, memory_write

## 卡点 / 不顺手的地方

finish_task 的相对测试路径在 backend cwd 下会找不到模块内测试，需要改用绝对路径；并行 worker dirty 会让模块边界检查整体失败，需人工区分来源。

## 缺少的工具 / 能力

希望 worktree_guard/finish_task 支持传入“本 agent touched files”或自动按 mtime/patch owner 标记并行 dirty。

## 升级建议

run_test 对模块目录可自动从 repo root 解析，或当目标以 modules/ 开头时不要切到 backend cwd 后直接相对执行。

## 建议移除或合并的工具

无

## 其他备注

本轮未回退任何并行改动；边界失败来自并行 dirty，K2 自身修改集中在 modules/knowledge。

## 当前工具热度快照

```json
[
  {
    "tool": "code_node",
    "calls": 137,
    "error": 0,
    "avg_duration_seconds": 0.14
  },
  {
    "tool": "lint",
    "calls": 125,
    "error": 0,
    "avg_duration_seconds": 0.016
  },
  {
    "tool": "sql",
    "calls": 109,
    "error": 3,
    "avg_duration_seconds": 0.031
  },
  {
    "tool": "code_explore",
    "calls": 79,
    "error": 0,
    "avg_duration_seconds": 0.304
  },
  {
    "tool": "worktree_guard",
    "calls": 47,
    "error": 0,
    "avg_duration_seconds": 0.03
  },
  {
    "tool": "probe",
    "calls": 43,
    "error": 0,
    "avg_duration_seconds": 0.492
  },
  {
    "tool": "db_schema",
    "calls": 37,
    "error": 0,
    "avg_duration_seconds": 0.034
  },
  {
    "tool": "code_impact",
    "calls": 35,
    "error": 0,
    "avg_duration_seconds": 0.134
  },
  {
    "tool": "routes",
    "calls": 33,
    "error": 0,
    "avg_duration_seconds": 0.057
  },
  {
    "tool": "plan_task",
    "calls": 32,
    "error": 0,
    "avg_duration_seconds": 0.007
  }
]
```
