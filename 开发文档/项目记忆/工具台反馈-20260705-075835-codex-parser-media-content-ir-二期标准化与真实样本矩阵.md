---
name: "工具台反馈-20260705-075835-codex-Parser/Media Content IR 二期标准化与真实样本矩阵"
type: "reference"
tags: [mcp-feedback, dev-toolkit]
agent: "codex"
created: "2026-07-05T07:58:35.096813+00:00"
---

# MCP 使用反馈

## 任务

Parser/Media Content IR 二期标准化与真实样本矩阵；代码提交 859b9b12

## 顺畅度

- 评分：4/5
- 体感：整体顺畅，CodeGraph/工具台定位 Content IR 与模块边界很快。

## 本次用到的工具

brief, plan_task, worktree_guard, code_explore, code_node, code_impact, capabilities, routes, db_schema, lint, run_test, probe, tail_log, memory_write

## 卡点 / 不顺手的地方

lint 工具对带连字符的模块目录（modules/csv-parser 等）误判文件不存在；pytest 多个 sandbox/test_module.py 同进程运行会 import mismatch，需要 --import-mode=importlib 和额外 PYTHONPATH。

## 缺少的工具 / 能力

希望 run_test 支持多个同名 sandbox test_module.py 时自动使用 importlib 模式并补 sandbox 自身路径。

## 升级建议

lint 工具建议支持目录目标和连字符路径；module sandbox 组合测试可内置同名测试模块规避策略。

## 建议移除或合并的工具

无

## 其他备注

工作区另有 modules/memory/frontend/* 外部改动，未纳入本任务提交。

## 当前工具热度快照

```json
[
  {
    "tool": "code_node",
    "calls": 67,
    "error": 0,
    "avg_duration_seconds": 0.146
  },
  {
    "tool": "run_test",
    "calls": 64,
    "error": 0,
    "avg_duration_seconds": 3.218
  },
  {
    "tool": "probe",
    "calls": 63,
    "error": 3,
    "avg_duration_seconds": 0.263
  },
  {
    "tool": "code_impact",
    "calls": 36,
    "error": 0,
    "avg_duration_seconds": 0.134
  },
  {
    "tool": "worktree_guard",
    "calls": 32,
    "error": 0,
    "avg_duration_seconds": 0.03
  },
  {
    "tool": "lint",
    "calls": 29,
    "error": 0,
    "avg_duration_seconds": 0.093
  },
  {
    "tool": "sql",
    "calls": 25,
    "error": 4,
    "avg_duration_seconds": 0.03
  },
  {
    "tool": "code_explore",
    "calls": 18,
    "error": 1,
    "avg_duration_seconds": 0.349
  },
  {
    "tool": "finish_task",
    "calls": 17,
    "error": 0,
    "avg_duration_seconds": 1.344
  },
  {
    "tool": "brief",
    "calls": 15,
    "error": 0,
    "avg_duration_seconds": 0.817
  }
]
```
