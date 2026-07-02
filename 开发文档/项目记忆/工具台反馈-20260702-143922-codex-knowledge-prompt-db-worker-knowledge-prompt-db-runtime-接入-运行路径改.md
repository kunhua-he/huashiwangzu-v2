---
name: "工具台反馈-20260702-143922-codex-knowledge-prompt-db-worker-Knowledge Prompt DB runtime 接入：运行路径改"
type: "reference"
tags: [mcp-feedback, dev-toolkit]
agent: "codex-knowledge-prompt-db-worker"
created: "2026-07-02T14:39:22.425696+00:00"
---

# MCP 使用反馈

## 任务

Knowledge Prompt DB runtime 接入：运行路径改用 load_prompt，补 knowledge prompt seed 和 focused tests。

## 顺畅度

- 评分：4/5
- 体感：整体顺畅，codegraph 与工具台测试/lint 很快定位和验证。

## 本次用到的工具

brief, plan_task, worktree_guard, code_explore, code_node, code_impact, routes, capabilities, db_schema, lint, run_test, probe, tail_log, finish_task, memory_write

## 卡点 / 不顺手的地方

finish_task 的模块边界默认只允许 modules/knowledge，无法表达本任务用户明确允许 backend/tests，因此结果为 false；并行工作区脏文件也会让边界摘要噪声较大。

## 缺少的工具 / 能力

希望 worktree_guard/finish_task 支持额外 allowed_prefixes 与 module_key 叠加，避免允许测试文件的模块任务被误判。

## 升级建议

finish_task 的 boundary_check 可读取传入 lint/test targets 或显式 allowed_prefixes，并在报告里区分本次改动与预先存在的 dirty。

## 建议移除或合并的工具

无

## 其他备注

本次没有使用 quick_fix 工具，manual apply_patch 更适合多处签名和测试新增。

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
    "calls": 60,
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
    "calls": 50,
    "error": 0,
    "avg_duration_seconds": 0.489
  },
  {
    "tool": "routes",
    "calls": 43,
    "error": 0,
    "avg_duration_seconds": 0.061
  },
  {
    "tool": "plan_task",
    "calls": 42,
    "error": 0,
    "avg_duration_seconds": 0.008
  }
]
```
