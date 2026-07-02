---
name: "工具台反馈-20260702-143800-codex-agent-fallback-dedupe-worker-修复 Agent 双层模型 fallback，保留 wrapper 名称"
type: "reference"
tags: [mcp-feedback, dev-toolkit]
agent: "codex-agent-fallback-dedupe-worker"
created: "2026-07-02T14:38:00.724420+00:00"
---

# MCP 使用反馈

## 任务

修复 Agent 双层模型 fallback，保留 wrapper 名称但只调用 gateway 一次，并补 focused tests。

## 顺畅度

- 评分：4/5
- 体感：整体顺畅，brief/plan_task/code_explore/finish_task 对共享 worktree 场景很有帮助。

## 本次用到的工具

brief, plan_task, worktree_guard, code_explore, lint, run_test, finish_task, memory_write, mcp_feedback

## 卡点 / 不顺手的地方

lint 工具一次只接受单文件 path，我第一次传多个文件时失败；run_test 对模块外路径需要用 ../modules，提示可再直观些。

## 缺少的工具 / 能力

无

## 升级建议

lint 支持逗号或空格分隔多文件会更贴近 finish_task 的 lint_paths 行为；run_test 可在找不到 modules/... 时自动尝试 ../modules/...。

## 建议移除或合并的工具

无

## 其他备注

共享 worktree 下 finish_task 的边界失败可预期，最终仍需按本次限定 diff 人工区分外部 dirty。

## 当前工具热度快照

```json
[
  {
    "tool": "code_node",
    "calls": 189,
    "error": 0,
    "avg_duration_seconds": 0.139
  },
  {
    "tool": "lint",
    "calls": 178,
    "error": 0,
    "avg_duration_seconds": 0.016
  },
  {
    "tool": "sql",
    "calls": 139,
    "error": 5,
    "avg_duration_seconds": 0.031
  },
  {
    "tool": "code_explore",
    "calls": 109,
    "error": 0,
    "avg_duration_seconds": 0.302
  },
  {
    "tool": "worktree_guard",
    "calls": 58,
    "error": 0,
    "avg_duration_seconds": 0.029
  },
  {
    "tool": "code_impact",
    "calls": 52,
    "error": 0,
    "avg_duration_seconds": 0.132
  },
  {
    "tool": "db_schema",
    "calls": 50,
    "error": 0,
    "avg_duration_seconds": 0.033
  },
  {
    "tool": "probe",
    "calls": 49,
    "error": 0,
    "avg_duration_seconds": 0.492
  },
  {
    "tool": "routes",
    "calls": 43,
    "error": 0,
    "avg_duration_seconds": 0.061
  },
  {
    "tool": "plan_task",
    "calls": 41,
    "error": 0,
    "avg_duration_seconds": 0.009
  }
]
```
