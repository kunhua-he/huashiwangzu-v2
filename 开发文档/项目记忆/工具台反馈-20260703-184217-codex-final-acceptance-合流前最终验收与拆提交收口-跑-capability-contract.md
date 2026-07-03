---
name: "工具台反馈-20260703-184217-codex-final-acceptance-合流前最终验收与拆提交收口：跑 capability contract、"
type: "reference"
tags: [mcp-feedback, dev-toolkit]
agent: "codex-final-acceptance"
created: "2026-07-03T18:42:17.855307+00:00"
---

# MCP 使用反馈

## 任务

合流前最终验收与拆提交收口：跑 capability contract、module sandbox --check、parser/media 静态审计、lint、定向测试、UI 5.2 cleanup 与 release gate preflight。

## 顺畅度

- 评分：4/5
- 体感：整体顺畅，worktree_guard 与 capability_contract_diff 很有用；release_gate 能明确暴露活栈 BLOCKER。

## 本次用到的工具

brief, plan_task, worktree_guard, capability_contract_diff, code_explore, finish_task, memory_write, mcp_feedback

## 卡点 / 不顺手的地方

工作区有并行 agent 持续落文件，dirty 数从 50 变到 56，归因仍需人工解释；release_gate 的 BLOCKER 字段原因需要进一步追到活栈 audit 响应。

## 缺少的工具 / 能力

缺一个按时间/agent/文件来源自动生成拆 commit 分组的工具；也缺 release_gate blocker 一键追因到响应 JSON/schema diff 的诊断工具。

## 升级建议

worktree_guard 支持开工 baseline 快照并在收尾显示新增来源；release_gate 输出可以附带被判缺失的原始 audit summary keys。

## 建议移除或合并的工具

无

## 其他备注

无

## 当前工具热度快照

```json
[
  {
    "tool": "code_node",
    "calls": 1312,
    "error": 0,
    "avg_duration_seconds": 0.144
  },
  {
    "tool": "lint",
    "calls": 658,
    "error": 0,
    "avg_duration_seconds": 0.031
  },
  {
    "tool": "probe",
    "calls": 574,
    "error": 8,
    "avg_duration_seconds": 0.449
  },
  {
    "tool": "code_explore",
    "calls": 566,
    "error": 0,
    "avg_duration_seconds": 0.326
  },
  {
    "tool": "sql",
    "calls": 566,
    "error": 35,
    "avg_duration_seconds": 0.031
  },
  {
    "tool": "call_capability",
    "calls": 499,
    "error": 17,
    "avg_duration_seconds": 0.681
  },
  {
    "tool": "worktree_guard",
    "calls": 472,
    "error": 0,
    "avg_duration_seconds": 0.03
  },
  {
    "tool": "run_test",
    "calls": 469,
    "error": 3,
    "avg_duration_seconds": 4.428
  },
  {
    "tool": "code_impact",
    "calls": 456,
    "error": 0,
    "avg_duration_seconds": 0.134
  },
  {
    "tool": "db_schema",
    "calls": 370,
    "error": 0,
    "avg_duration_seconds": 0.033
  }
]
```
