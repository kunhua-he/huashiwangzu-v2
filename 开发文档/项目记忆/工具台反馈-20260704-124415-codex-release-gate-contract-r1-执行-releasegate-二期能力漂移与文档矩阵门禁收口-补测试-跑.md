---
name: "工具台反馈-20260704-124415-codex-release-gate-contract-r1-执行 ReleaseGate 二期能力漂移与文档矩阵门禁收口，补测试、跑"
type: "reference"
tags: [mcp-feedback, dev-toolkit]
agent: "codex-release-gate-contract-r1"
created: "2026-07-04T12:44:15.468899+00:00"
---

# MCP 使用反馈

## 任务

执行 ReleaseGate 二期能力漂移与文档矩阵门禁收口，补测试、跑验收、跑活栈 gate 并记录真实 BLOCKER。

## 顺畅度

- 评分：4/5
- 体感：整体顺畅，release_gate 的结构化输出足够用于直接收口和定位 blocker/debt。

## 本次用到的工具

release_gate
worktree_guard
finish_task
memory_write
mcp_feedback

## 卡点 / 不顺手的地方

finish_task 的 forbidden_prefixes 不是显式 schema 字段，需先单独跑 worktree_guard 才能表达执行信的额外禁止边界。

## 缺少的工具 / 能力

希望 release_gate 可选输出更短的 machine summary，避免完整 JSON 太长。

## 升级建议

finish_task 可增加 forbidden_prefixes 字段，或在结果中明确展示用户传入的额外禁止边界。

## 建议移除或合并的工具

无

## 其他备注

本轮 gate 返回 BLOCKER 是预期发现：terminal-tools/web-tools background-service component_key 存量契约问题；因 modules/ 禁止修改，仅记录。

## 当前工具热度快照

```json
[
  {
    "tool": "code_node",
    "calls": 358,
    "error": 0,
    "avg_duration_seconds": 0.141
  },
  {
    "tool": "code_explore",
    "calls": 211,
    "error": 0,
    "avg_duration_seconds": 0.336
  },
  {
    "tool": "probe",
    "calls": 153,
    "error": 4,
    "avg_duration_seconds": 0.321
  },
  {
    "tool": "worktree_guard",
    "calls": 147,
    "error": 0,
    "avg_duration_seconds": 0.03
  },
  {
    "tool": "brief",
    "calls": 113,
    "error": 0,
    "avg_duration_seconds": 0.756
  },
  {
    "tool": "plan_task",
    "calls": 112,
    "error": 0,
    "avg_duration_seconds": 0.005
  },
  {
    "tool": "sql",
    "calls": 108,
    "error": 4,
    "avg_duration_seconds": 0.03
  },
  {
    "tool": "code_impact",
    "calls": 107,
    "error": 0,
    "avg_duration_seconds": 0.129
  },
  {
    "tool": "call_capability",
    "calls": 106,
    "error": 5,
    "avg_duration_seconds": 0.291
  },
  {
    "tool": "finish_task",
    "calls": 73,
    "error": 0,
    "avg_duration_seconds": 1.907
  }
]
```
