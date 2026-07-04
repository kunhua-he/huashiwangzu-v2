---
name: "工具台反馈-20260704-122835-codex-验收并提交并行回信批次，推送 GitHub 分支 codex/valid"
type: "reference"
tags: [mcp-feedback, dev-toolkit]
agent: "codex"
created: "2026-07-04T12:28:35.813013+00:00"
---

# MCP 使用反馈

## 任务

验收并提交并行回信批次，推送 GitHub 分支 codex/validated-returned-batch-20260704

## 顺畅度

- 评分：4/5
- 体感：整体顺畅，worktree_guard、lint、run_test、release_gate 能快速给出可提交证据。

## 本次用到的工具

worktree_guard, snap_diff, lint, run_test, release_gate, finish_task, memory_write, mcp_feedback

## 卡点 / 不顺手的地方

finish_task 输出过长且 success=false 主要因为 dirty 未提交，实际边界与验证已通过；大批量中文文件路径输出噪声较大。

## 缺少的工具 / 能力

希望有按执行信/回信文件自动聚类 dirty 文件并生成建议 commit 分组的工具。

## 升级建议

为 finish_task 增加 compact 模式；为 worktree_guard 增加按目录/任务关键词聚类与中文路径简化显示。

## 建议移除或合并的工具

无

## 其他备注

本次先分支提交并推送，避免直接污染 main。

## 当前工具热度快照

```json
[
  {
    "tool": "code_node",
    "calls": 329,
    "error": 0,
    "avg_duration_seconds": 0.141
  },
  {
    "tool": "code_explore",
    "calls": 198,
    "error": 0,
    "avg_duration_seconds": 0.337
  },
  {
    "tool": "probe",
    "calls": 148,
    "error": 4,
    "avg_duration_seconds": 0.323
  },
  {
    "tool": "worktree_guard",
    "calls": 139,
    "error": 0,
    "avg_duration_seconds": 0.03
  },
  {
    "tool": "brief",
    "calls": 108,
    "error": 0,
    "avg_duration_seconds": 0.753
  },
  {
    "tool": "plan_task",
    "calls": 107,
    "error": 0,
    "avg_duration_seconds": 0.005
  },
  {
    "tool": "call_capability",
    "calls": 104,
    "error": 5,
    "avg_duration_seconds": 0.291
  },
  {
    "tool": "code_impact",
    "calls": 103,
    "error": 0,
    "avg_duration_seconds": 0.129
  },
  {
    "tool": "sql",
    "calls": 99,
    "error": 4,
    "avg_duration_seconds": 0.03
  },
  {
    "tool": "run_test",
    "calls": 72,
    "error": 0,
    "avg_duration_seconds": 4.612
  }
]
```
