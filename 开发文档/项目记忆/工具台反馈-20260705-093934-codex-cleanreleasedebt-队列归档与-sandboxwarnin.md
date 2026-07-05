---
name: "工具台反馈-20260705-093934-codex-CleanReleaseDebt 队列归档与 SandboxWarnin"
type: "reference"
tags: [mcp-feedback, dev-toolkit]
agent: "codex"
created: "2026-07-05T09:39:34.108790+00:00"
---

# MCP 使用反馈

## 任务

CleanReleaseDebt 队列归档与 SandboxWarning 清零收口，最终 full release gate PASS 且 live queue/lifecycle 全零。

## 顺畅度

- 评分：3/5
- 体感：核心 dev_toolkit 本地 helper 可用，但 MCP stdio brief/plan_task/worktree_guard 多次 Transport closed。

## 本次用到的工具

codegraph CLI, dev_toolkit smoke probe, release_gate CLI, memory_write local helper, mcp_feedback local helper

## 卡点 / 不顺手的地方

项目工具台 MCP 工具发现后调用仍 Transport closed，只能改用 CLI/本地 helper；长 gate 过程会反复产生 obsolete queue，需要最终归档。

## 缺少的工具 / 能力

希望 release_gate PASS 后可选自动调用 governance 归档 gate 内产生的 deleted-source obsolete，并输出最终 live queue zero 证据。

## 升级建议

为 UI gate 增加 admin token 复用/跨 worker 登录失效诊断；为 content artifact cleanup 提供测试侧 lifecycle 清理 helper。

## 建议移除或合并的工具

无

## 其他备注

遵守禁改 ui-e2e.spec.mjs；实际修复落在共享测试 helper 和非禁区 content artifact 测试。

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
    "calls": 41,
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
    "calls": 25,
    "error": 1,
    "avg_duration_seconds": 0.347
  },
  {
    "tool": "finish_task",
    "calls": 24,
    "error": 0,
    "avg_duration_seconds": 1.017
  }
]
```
