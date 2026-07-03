---
name: "工具台反馈-20260703-160537-codex-r6-media-local-facts-c-media-intelligence 本地事实层第一刀：替换 local"
type: "reference"
tags: [mcp-feedback, dev-toolkit]
agent: "codex-r6-media-local-facts-c"
created: "2026-07-03T16:05:37.820206+00:00"
---

# MCP 使用反馈

## 任务

media-intelligence 本地事实层第一刀：替换 local_algorithms.placeholder，接 Pillow/ffprobe metadata/facts，缺依赖结构化 degraded，补 sandbox 测试。

## 顺畅度

- 评分：4/5
- 体感：整体顺畅：brief/plan_task/code_explore/impact/lint/run_test/probe/finish_task 串起来有效。

## 本次用到的工具

brief, plan_task, worktree_guard, code_explore, code_node, code_impact, routes, capabilities, db_schema, lint, run_test, probe, tail_log, finish_task, memory_write

## 卡点 / 不顺手的地方

finish_task/worktree_guard 在多 worker 并发改同一仓库时无法区分本 agent 改动与其他 agent 新增 dirty，只能整体标红。

## 缺少的工具 / 能力

希望有基于进程/agent 的 changed-files 记录或可声明并发外部 dirty 的 guard 模式。

## 升级建议

worktree_guard 支持传入“本任务实际 touched files”并单独输出 own_scope_pass，会更适合多 worker 并行批次。

## 建议移除或合并的工具

无

## 其他备注

CodeGraph 定位 provider/pipeline 链路很快；run_test 首次暴露 sandbox PYTHONPATH 问题，已在模块测试里修复。

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
    "calls": 504,
    "error": 6,
    "avg_duration_seconds": 0.446
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
    "calls": 406,
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
