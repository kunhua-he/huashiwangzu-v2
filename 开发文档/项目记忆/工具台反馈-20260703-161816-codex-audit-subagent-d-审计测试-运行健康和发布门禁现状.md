---
name: "工具台反馈-20260703-161816-codex-audit-subagent-d-审计测试/运行健康和发布门禁现状"
type: "reference"
tags: [mcp-feedback, dev-toolkit]
agent: "codex-audit-subagent-d"
created: "2026-07-03T16:18:16.579097+00:00"
---

# MCP 使用反馈

## 任务

审计测试/运行健康和发布门禁现状

## 顺畅度

- 评分：4/5
- 体感：整体顺畅，release_gate/smoke 输出结构化 JSON 很好用。

## 本次用到的工具

brief, worktree_guard, probe, routes, capabilities, db_schema, release_gate, smoke_all, run_test, lint, finish_task, memory_write, mcp_feedback

## 卡点 / 不顺手的地方

probe 大响应会截断，队列审计需要多次选择性读取；capabilities 全量输出过长且容易截断。

## 缺少的工具 / 能力

希望增加 task_queue_audit 专用 MCP 工具，可直接返回 summary/classification/top signatures/samples 的紧凑 JSON；希望 release_gate 支持 skip_ui=false 作为显式参数输出 UI 细分结果。

## 升级建议

release_gate 的 MCP 响应 success=false 表达 clean_pass=false，容易被误解为工具失败；建议增加 tool_success 与 gate_success 分离字段。

## 建议移除或合并的工具

无

## 其他备注

真实 Playwright 发现 UI 删除/回收链路红点，说明 skip-ui 门禁只能作为后端门禁。

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
    "calls": 645,
    "error": 0,
    "avg_duration_seconds": 0.031
  },
  {
    "tool": "probe",
    "calls": 537,
    "error": 8,
    "avg_duration_seconds": 0.449
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
