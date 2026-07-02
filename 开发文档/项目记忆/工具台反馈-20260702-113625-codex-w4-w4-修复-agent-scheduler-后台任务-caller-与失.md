---
name: "工具台反馈-20260702-113625-codex-w4-W4 修复 Agent/Scheduler 后台任务 caller 与失"
type: "reference"
tags: [mcp-feedback, dev-toolkit]
agent: "codex-w4"
created: "2026-07-02T11:36:25.561418+00:00"
---

# MCP 使用反馈

## 任务

W4 修复 Agent/Scheduler 后台任务 caller 与失败语义，补 slow tool 失败语义和 subagent owner_id 测试。

## 顺畅度

- 评分：4/5
- 体感：整体顺畅：brief/plan/codegraph/lint/run_test/finish_task 都能支撑并行修复工作。

## 本次用到的工具

brief, plan_task, worktree_guard, code_explore, code_node, code_impact, routes, capabilities, db_schema, lint, run_test, finish_task, memory_write

## 卡点 / 不顺手的地方

worktree_guard/finish_task 在多代理 dirty 工作区会汇总大量无关变更，最终边界需要人工按本次触碰文件解释。run_test 对 repo 外层 modules 路径需要传绝对路径才稳定。

## 缺少的工具 / 能力

如果 finish_task 支持 allowed_prefixes 而不只 module_key，会更适合这种跨 agent+scheduler 的小修。

## 升级建议

run_test 可自动识别 repo 根路径下 modules/...，避免从 backend cwd 拼错路径。finish_task 可接受 allowed_prefixes 并输出本次工具会话触碰文件快照。

## 建议移除或合并的工具

无

## 其他备注

本次没有用 probe，因为修复点是后台 handler 单元语义，已用 monkeypatch 单测覆盖。

## 当前工具热度快照

```json
[
  {
    "tool": "code_node",
    "calls": 111,
    "error": 0,
    "avg_duration_seconds": 0.139
  },
  {
    "tool": "lint",
    "calls": 65,
    "error": 0,
    "avg_duration_seconds": 0.017
  },
  {
    "tool": "code_explore",
    "calls": 56,
    "error": 0,
    "avg_duration_seconds": 0.305
  },
  {
    "tool": "sql",
    "calls": 50,
    "error": 0,
    "avg_duration_seconds": 0.033
  },
  {
    "tool": "worktree_guard",
    "calls": 35,
    "error": 0,
    "avg_duration_seconds": 0.031
  },
  {
    "tool": "code_impact",
    "calls": 30,
    "error": 0,
    "avg_duration_seconds": 0.136
  },
  {
    "tool": "db_schema",
    "calls": 27,
    "error": 0,
    "avg_duration_seconds": 0.033
  },
  {
    "tool": "plan_task",
    "calls": 25,
    "error": 0,
    "avg_duration_seconds": 0.005
  },
  {
    "tool": "routes",
    "calls": 25,
    "error": 0,
    "avg_duration_seconds": 0.048
  },
  {
    "tool": "probe",
    "calls": 24,
    "error": 0,
    "avg_duration_seconds": 0.593
  }
]
```
