---
name: "工具台反馈-20260702-103056-parallel-repair-worker-a-codex-修复 Content IR write_ir file_id 权限校验与"
type: "reference"
tags: [mcp-feedback, dev-toolkit]
agent: "parallel-repair-worker-a-codex"
created: "2026-07-02T10:30:56.001493+00:00"
---

# MCP 使用反馈

## 任务

修复 Content IR write_ir file_id 权限校验与资源持久化

## 顺畅度

- 评分：4/5
- 体感：整体顺畅，CodeGraph 和 run_test/lint 对本次修复很高效。

## 本次用到的工具

brief,plan_task,worktree_guard,code_explore,code_node,code_impact,routes,capabilities,db_schema,sql,lint,run_test,probe,tail_log,finish_task,memory_write,mcp_feedback

## 卡点 / 不顺手的地方

并行工作区下 worktree_guard 会把其他 worker 的脏文件一起判 outside_allowed，最终状态需要人工区分本 worker 的目标路径和全局 dirty。

## 缺少的工具 / 能力

如果有按 agent/session 标记的 dirty 归因工具，会更适合并行维修。

## 升级建议

worktree_guard/finish_task 可增加 baseline 参数，用开工时 dirty 快照过滤非本 agent 新增变更。

## 建议移除或合并的工具

无

## 其他备注

未重启常驻后端，避免影响并行 worker；用 pytest 验证新代码，probe health 验证活栈状态。

## 当前工具热度快照

```json
[
  {
    "tool": "code_node",
    "calls": 37,
    "error": 0,
    "avg_duration_seconds": 0.14
  },
  {
    "tool": "lint",
    "calls": 34,
    "error": 0,
    "avg_duration_seconds": 0.017
  },
  {
    "tool": "code_explore",
    "calls": 22,
    "error": 0,
    "avg_duration_seconds": 0.302
  },
  {
    "tool": "worktree_guard",
    "calls": 21,
    "error": 0,
    "avg_duration_seconds": 0.032
  },
  {
    "tool": "code_impact",
    "calls": 17,
    "error": 0,
    "avg_duration_seconds": 0.129
  },
  {
    "tool": "plan_task",
    "calls": 12,
    "error": 0,
    "avg_duration_seconds": 0.005
  },
  {
    "tool": "db_schema",
    "calls": 10,
    "error": 0,
    "avg_duration_seconds": 0.034
  },
  {
    "tool": "finish_task",
    "calls": 10,
    "error": 0,
    "avg_duration_seconds": 1.448
  },
  {
    "tool": "mcp_feedback",
    "calls": 10,
    "error": 0,
    "avg_duration_seconds": 0.012
  },
  {
    "tool": "memory_write",
    "calls": 10,
    "error": 0,
    "avg_duration_seconds": 0.606
  }
]
```
