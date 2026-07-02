---
name: "工具台反馈-20260702-114535-W3-codex-修复 excel-engine state_key owner 隔离、k"
type: "reference"
tags: [mcp-feedback, dev-toolkit]
agent: "W3-codex"
created: "2026-07-02T11:45:35.941555+00:00"
---

# MCP 使用反馈

## 任务

修复 excel-engine state_key owner 隔离、knowledge 文件权限校验和 version_id IDOR

## 顺畅度

- 评分：4/5
- 体感：整体顺畅；工具发现后项目工具台可用，finish_task 的 lint/test 汇总很好用。

## 本次用到的工具

codegraph CLI, finish_task, memory_write, mcp_feedback, ruff, pytest

## 卡点 / 不顺手的地方

项目工具台 MCP 不是初始暴露，需要先用 tool_search 才能拿到；finish_task 在并行多人脏工作区下会把既有外部 dirty 标为边界失败，需要人工解释。

## 缺少的工具 / 能力

希望 worktree_guard/finish_task 支持传入本任务 touched file allowlist 或 baseline dirty snapshot，区分开工前脏改与本任务新增改动。

## 升级建议

为模块任务增加“仅校验本任务新增/修改文件”的边界模式；finish_task 可接受 pre_dirty 快照或 changed_since timestamp。

## 建议移除或合并的工具

无

## 其他备注

本次测试使用 sandbox + pytest 双模式，并查询确认 DB 测试数据清零。

## 当前工具热度快照

```json
[
  {
    "tool": "code_node",
    "calls": 118,
    "error": 0,
    "avg_duration_seconds": 0.14
  },
  {
    "tool": "lint",
    "calls": 81,
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
    "tool": "probe",
    "calls": 26,
    "error": 0,
    "avg_duration_seconds": 0.571
  },
  {
    "tool": "routes",
    "calls": 26,
    "error": 0,
    "avg_duration_seconds": 0.047
  }
]
```
