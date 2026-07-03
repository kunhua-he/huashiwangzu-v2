---
name: "工具台反馈-20260703-161724-codex-audit-subagent-c-只读审计 modules/media-intelligence 当前改动"
type: "reference"
tags: [mcp-feedback, dev-toolkit]
agent: "codex-audit-subagent-c"
created: "2026-07-03T16:17:24.102640+00:00"
---

# MCP 使用反馈

## 任务

只读审计 modules/media-intelligence 当前改动真实成熟度、假成功风险、边界和返工原因

## 顺畅度

- 评分：4/5
- 体感：整体顺畅，brief/plan_task/codegraph/routes/capabilities/probe/call_capability 足够支撑只读审计。

## 本次用到的工具

brief, plan_task, worktree_guard, code_explore, code_node, code_impact, capabilities, routes, tail_log, probe, call_capability, finish_task, memory_write

## 卡点 / 不顺手的地方

finish_task 未传开工 baseline 时会把并发 worker 既有 dirty 全算作边界违规；只读审计场景需要更轻量的 baseline 自动继承。

## 缺少的工具 / 能力

缺少按模块生成“HTTP success 但 stage degraded/artifact empty”风险矩阵的专用审计工具。

## 升级建议

给 module capability 增加一键 maturity probe：自动调用 analysis-only、invalid params、已有文件样例，并汇总 outer_success/inner_status/degraded/artifacts。

## 建议移除或合并的工具

无

## 其他备注

本次未修改产品代码；按 AGENTS 写入项目记忆和反馈。

## 当前工具热度快照

```json
[
  {
    "tool": "code_node",
    "calls": 1211,
    "error": 0,
    "avg_duration_seconds": 0.144
  },
  {
    "tool": "lint",
    "calls": 644,
    "error": 0,
    "avg_duration_seconds": 0.031
  },
  {
    "tool": "probe",
    "calls": 536,
    "error": 8,
    "avg_duration_seconds": 0.45
  },
  {
    "tool": "sql",
    "calls": 525,
    "error": 28,
    "avg_duration_seconds": 0.03
  },
  {
    "tool": "code_explore",
    "calls": 501,
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
    "calls": 444,
    "error": 2,
    "avg_duration_seconds": 3.873
  },
  {
    "tool": "code_impact",
    "calls": 428,
    "error": 0,
    "avg_duration_seconds": 0.134
  },
  {
    "tool": "worktree_guard",
    "calls": 414,
    "error": 0,
    "avg_duration_seconds": 0.03
  },
  {
    "tool": "db_schema",
    "calls": 358,
    "error": 0,
    "avg_duration_seconds": 0.033
  }
]
```
