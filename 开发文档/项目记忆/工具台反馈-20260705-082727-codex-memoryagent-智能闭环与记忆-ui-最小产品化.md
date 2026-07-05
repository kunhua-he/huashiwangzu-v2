---
name: "工具台反馈-20260705-082727-codex-MemoryAgent 智能闭环与记忆 UI 最小产品化"
type: "reference"
tags: [mcp-feedback, dev-toolkit]
agent: "codex"
created: "2026-07-05T08:27:27.231126+00:00"
---

# MCP 使用反馈

## 任务

MemoryAgent 智能闭环与记忆 UI 最小产品化

## 顺畅度

- 评分：4/5
- 体感：整体顺畅，brief/plan_task/codegraph/capability/probe 对快速定边界很有帮助。

## 本次用到的工具

brief, plan_task, worktree_guard, code_explore, code_node, code_impact, routes, capabilities, db_schema, call_capability, probe, tail_log, finish_task, memory_write, mcp_feedback

## 卡点 / 不顺手的地方

worktree_guard 无法自动区分并发 agent 在任务中途产生的 dirty，需要手动 baseline 排除；浏览器工具 DOM snapshot/localStorage/fetch 能力不稳定，前端视觉冒烟成本偏高。

## 缺少的工具 / 能力

希望有 mailbox_create_delivery_bundle/check_delivery_bundle 的直接可用工具，以及可返回当前登录 token 状态但不泄露 token 的安全浏览器探针。

## 升级建议

finish_task 可以支持标记“并发外部 dirty”并自动生成提交排除清单；browser 插件可增加 localhost app 的安全 auth-state 诊断摘要。

## 建议移除或合并的工具

无

## 其他备注

本次未修改框架 backend/app 或 frontend/src；Memory 后端能力足够，未新增后端 capability。

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
    "calls": 39,
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
    "tool": "finish_task",
    "calls": 23,
    "error": 0,
    "avg_duration_seconds": 1.059
  }
]
```
