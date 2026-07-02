---
name: "工具台反馈-20260702-140743-codex-conductor-模型网关本地降级与知识库 ingest/status/pipeline/"
type: "reference"
tags: [mcp-feedback, dev-toolkit]
agent: "codex-conductor"
created: "2026-07-02T14:07:43.505944+00:00"
---

# MCP 使用反馈

## 任务

模型网关本地降级与知识库 ingest/status/pipeline/search 专项收口

## 顺畅度

- 评分：4/5
- 体感：整体顺畅，brief/plan/worktree_guard/codegraph/release_gate 对主会话指挥很有帮助。

## 本次用到的工具

brief, plan_task, worktree_guard, code_explore, code_node, code_impact, lint, finish_task, memory_write, mcp_feedback, sql, tail_log, _restart_backend

## 卡点 / 不顺手的地方

finish_task 的 test_targets 传入 backend/tests 与 modules/knowledge 混合路径时，从 backend cwd 归一化失败，误报 modules/knowledge 路径不存在；实际 shell 分组测试已通过。

## 缺少的工具 / 能力

希望 run_test/finish_task 支持 repo-root 相对路径和 backend cwd 路径混跑，并能按分组隔离 pytest 进程，避免模块动态加载双 import。

## 升级建议

release_gate 可输出最近 failed task 的 task_type/top error 摘要，方便区分历史债与本次新增债。

## 建议移除或合并的工具

无

## 其他备注

K3 子代理超时，但主会话接管其检索污染改动并补齐验证。

## 当前工具热度快照

```json
[
  {
    "tool": "lint",
    "calls": 146,
    "error": 0,
    "avg_duration_seconds": 0.016
  },
  {
    "tool": "code_node",
    "calls": 143,
    "error": 0,
    "avg_duration_seconds": 0.14
  },
  {
    "tool": "sql",
    "calls": 112,
    "error": 3,
    "avg_duration_seconds": 0.031
  },
  {
    "tool": "code_explore",
    "calls": 84,
    "error": 0,
    "avg_duration_seconds": 0.302
  },
  {
    "tool": "worktree_guard",
    "calls": 49,
    "error": 0,
    "avg_duration_seconds": 0.03
  },
  {
    "tool": "probe",
    "calls": 43,
    "error": 0,
    "avg_duration_seconds": 0.492
  },
  {
    "tool": "code_impact",
    "calls": 37,
    "error": 0,
    "avg_duration_seconds": 0.133
  },
  {
    "tool": "db_schema",
    "calls": 37,
    "error": 0,
    "avg_duration_seconds": 0.034
  },
  {
    "tool": "routes",
    "calls": 34,
    "error": 0,
    "avg_duration_seconds": 0.056
  },
  {
    "tool": "plan_task",
    "calls": 33,
    "error": 0,
    "avg_duration_seconds": 0.007
  }
]
```
