---
name: "工具台反馈-20260703-160630-codex-r6-algorithm-research-R6算法研究专线：图片、视频、知识库算法路线研究并写入项目记忆报告。"
type: "reference"
tags: [mcp-feedback, dev-toolkit]
agent: "codex-r6-algorithm-research"
created: "2026-07-03T16:06:30.702768+00:00"
---

# MCP 使用反馈

## 任务

R6算法研究专线：图片、视频、知识库算法路线研究并写入项目记忆报告。

## 顺畅度

- 评分：4/5
- 体感：整体顺畅，codegraph/code_node/capabilities/db_schema/probe 能快速拼出现状证据。

## 本次用到的工具

brief, plan_task, worktree_guard, code_explore, code_node, capabilities, routes, db_schema, probe, tail_log, finish_task, memory_write

## 卡点 / 不顺手的地方

worktree_guard 未传开工 baseline 时会把其他线程既有改动算入本轮越界；memory_write 返回的相对路径与直接 sed 定位出现一次不一致，需要再用 find 确认。

## 缺少的工具 / 能力

希望 memory_write 返回绝对路径并可选回读预览；worktree_guard 支持将首次 guard 输出直接作为后续 finish baseline 更顺。

## 升级建议

finish_task 若检测到存在开工前 dirty，可提示使用 baseline_status_json，并区分本轮新增与既有 dirty。

## 建议移除或合并的工具

无

## 其他备注

本轮只读研究为主，未修改主项目代码；仅通过 memory_write 写项目记忆。

## 当前工具热度快照

```json
[
  {
    "tool": "code_node",
    "calls": 1197,
    "error": 0,
    "avg_duration_seconds": 0.144
  },
  {
    "tool": "lint",
    "calls": 640,
    "error": 0,
    "avg_duration_seconds": 0.03
  },
  {
    "tool": "sql",
    "calls": 515,
    "error": 25,
    "avg_duration_seconds": 0.031
  },
  {
    "tool": "probe",
    "calls": 508,
    "error": 6,
    "avg_duration_seconds": 0.447
  },
  {
    "tool": "code_explore",
    "calls": 488,
    "error": 0,
    "avg_duration_seconds": 0.326
  },
  {
    "tool": "call_capability",
    "calls": 475,
    "error": 17,
    "avg_duration_seconds": 0.697
  },
  {
    "tool": "run_test",
    "calls": 432,
    "error": 2,
    "avg_duration_seconds": 3.83
  },
  {
    "tool": "code_impact",
    "calls": 422,
    "error": 0,
    "avg_duration_seconds": 0.134
  },
  {
    "tool": "worktree_guard",
    "calls": 408,
    "error": 0,
    "avg_duration_seconds": 0.03
  },
  {
    "tool": "db_schema",
    "calls": 351,
    "error": 0,
    "avg_duration_seconds": 0.033
  }
]
```
