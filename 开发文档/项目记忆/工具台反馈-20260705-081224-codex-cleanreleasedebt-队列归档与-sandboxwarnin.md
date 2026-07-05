---
name: "工具台反馈-20260705-081224-codex-CleanReleaseDebt 队列归档与 SandboxWarnin"
type: "reference"
tags: [mcp-feedback, dev-toolkit]
agent: "codex"
created: "2026-07-05T08:12:24.268581+00:00"
---

# MCP 使用反馈

## 任务

CleanReleaseDebt 队列归档与 SandboxWarning 清零收口续跑

## 顺畅度

- 评分：3/5
- 体感：MCP stdio 仍 transport closed；本地函数兜底可用。

## 本次用到的工具

local CLI, codegraph CLI, release_gate, module_sandbox_matrix, ruff, pytest, memory_tools/mailbox_tools

## 卡点 / 不顺手的地方

MCP transport closed，无法通过工具调用 memory_write/mailbox。

## 缺少的工具 / 能力

需要工具台 stdio 长任务隔离或自动重连。

## 升级建议

给 memory/mailbox/finish_task 提供正式 CLI 兜底。

## 建议移除或合并的工具

无

## 其他备注

full gate 无 blocker，但外部 dirty 阻止 clean_release_ready=true。

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
