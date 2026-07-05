---
name: "工具台反馈-20260705-081319-codex-office-gen 与 excel-engine Office 产品化"
type: "reference"
tags: [mcp-feedback, dev-toolkit]
agent: "codex"
created: "2026-07-05T08:13:19.175131+00:00"
---

# MCP 使用反馈

## 任务

office-gen 与 excel-engine Office 产品化闭环增强、验收、清理测试产物并准备提交

## 顺畅度

- 评分：4/5
- 体感：整体顺畅，CodeGraph 和能力/路由查询帮助快速锁定边界，probe/call_capability 活系统验证很直接。

## 本次用到的工具

brief, plan_task, worktree_guard, code_explore, code_node, code_impact, capabilities, routes, db_schema, lint, run_test, probe, call_capability, capability_contract_diff, tail_log, memory_write

## 卡点 / 不顺手的地方

lint 工具传目录时误报“文件不存在”，需要回退原生 ruff；两个同名 sandbox/test_module.py 默认 pytest 合跑会 import mismatch，需要 --import-mode=importlib。

## 缺少的工具 / 能力

无阻塞；若 mailbox 工具能自动带 commit hash 或从验证结果生成更完整五件套会更省心。

## 升级建议

lint 工具支持目录和带 hyphen 的模块路径；run_test 支持多个同名 test_module.py 时自动加 --import-mode=importlib 或提示。

## 建议移除或合并的工具

无

## 其他备注

本次未修改框架；开工前已有 agent/memory dirty 和其他任务未跟踪项目记忆，未纳入提交。

## 当前工具热度快照

```json
[
  {
    "tool": "code_node",
    "calls": 96,
    "error": 0,
    "avg_duration_seconds": 0.143
  },
  {
    "tool": "probe",
    "calls": 81,
    "error": 3,
    "avg_duration_seconds": 0.268
  },
  {
    "tool": "run_test",
    "calls": 67,
    "error": 0,
    "avg_duration_seconds": 3.117
  },
  {
    "tool": "code_impact",
    "calls": 46,
    "error": 0,
    "avg_duration_seconds": 0.134
  },
  {
    "tool": "worktree_guard",
    "calls": 38,
    "error": 0,
    "avg_duration_seconds": 0.03
  },
  {
    "tool": "sql",
    "calls": 37,
    "error": 6,
    "avg_duration_seconds": 0.03
  },
  {
    "tool": "lint",
    "calls": 32,
    "error": 0,
    "avg_duration_seconds": 0.086
  },
  {
    "tool": "call_capability",
    "calls": 28,
    "error": 0,
    "avg_duration_seconds": 0.524
  },
  {
    "tool": "code_explore",
    "calls": 24,
    "error": 1,
    "avg_duration_seconds": 0.347
  },
  {
    "tool": "capabilities",
    "calls": 22,
    "error": 0,
    "avg_duration_seconds": 0.001
  }
]
```
