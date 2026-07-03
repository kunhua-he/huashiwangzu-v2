---
name: "工具台反馈-20260703-171538-codex-convergence-reset-worker-加固 reset runtime 维护脚本并补充 fake/monkey"
type: "reference"
tags: [mcp-feedback, dev-toolkit]
agent: "codex-convergence-reset-worker"
created: "2026-07-03T17:15:38.016100+00:00"
---

# MCP 使用反馈

## 任务

加固 reset runtime 维护脚本并补充 fake/monkeypatch 单测

## 顺畅度

- 评分：4/5
- 体感：整体顺畅，brief/plan/codegraph/finish_task 能快速建立边界和验收记录。

## 本次用到的工具

brief, plan_task, worktree_guard, code_explore, code_node, code_impact, lint, run_test, finish_task, memory_write, mcp_feedback

## 卡点 / 不顺手的地方

worktree_guard/finish_task 在并行代理场景下会把他人新增 dirty 文件也计入 outside_allowed，需要人工解释。

## 缺少的工具 / 能力

无

## 升级建议

finish_task 可支持传入“并行代理改动白名单/本轮触碰文件列表”，让边界结论更贴近多人并发维修。

## 建议移除或合并的工具

无

## 其他备注

测试实际使用 fake asyncpg 连接和临时目录，不碰真实 DB、不删除真实 runtime 文件。

## 当前工具热度快照

```json
[
  {
    "tool": "code_node",
    "calls": 1228,
    "error": 0,
    "avg_duration_seconds": 0.144
  },
  {
    "tool": "lint",
    "calls": 649,
    "error": 0,
    "avg_duration_seconds": 0.031
  },
  {
    "tool": "probe",
    "calls": 544,
    "error": 8,
    "avg_duration_seconds": 0.451
  },
  {
    "tool": "sql",
    "calls": 535,
    "error": 30,
    "avg_duration_seconds": 0.03
  },
  {
    "tool": "code_explore",
    "calls": 515,
    "error": 0,
    "avg_duration_seconds": 0.326
  },
  {
    "tool": "call_capability",
    "calls": 495,
    "error": 17,
    "avg_duration_seconds": 0.684
  },
  {
    "tool": "run_test",
    "calls": 448,
    "error": 2,
    "avg_duration_seconds": 4.543
  },
  {
    "tool": "code_impact",
    "calls": 438,
    "error": 0,
    "avg_duration_seconds": 0.134
  },
  {
    "tool": "worktree_guard",
    "calls": 428,
    "error": 0,
    "avg_duration_seconds": 0.03
  },
  {
    "tool": "db_schema",
    "calls": 362,
    "error": 0,
    "avg_duration_seconds": 0.033
  }
]
```
