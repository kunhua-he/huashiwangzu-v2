---
name: "工具台反馈-20260702-115843-codex-w8-修复 memory_experiences owner/scope 隔离"
type: "reference"
tags: [mcp-feedback, dev-toolkit]
agent: "codex-w8"
created: "2026-07-02T11:58:43.800842+00:00"
---

# MCP 使用反馈

## 任务

修复 memory_experiences owner/scope 隔离、feedback 原子计数和 dream/link 重复软修

## 顺畅度

- 评分：4/5
- 体感：整体顺畅，brief/plan/worktree_guard/codegraph/run_test/lint/finish_task 串起来很省心。

## 本次用到的工具

brief, plan_task, worktree_guard, code_explore, code_node, code_impact, routes, capabilities, db_schema, lint, run_test, probe, call_capability, tail_log, finish_task, memory_write

## 卡点 / 不顺手的地方

worktree_guard/finish_task 在共享工作区会把其他 agent 的改动一起算作 outside_allowed，最终状态需要人工解释；live call_capability 打的是未重启常驻后端，容易误判当前源码。

## 缺少的工具 / 能力

希望有一个“只校验本轮 touched files”的边界工具，或允许传 explicit changed_files baseline；也希望 call_capability 能标注当前后端进程代码版本/启动时间。

## 升级建议

finish_task 可以接受额外 allowed_prefixes，以便模块任务允许新增特定 backend/tests 文件；probe/call_capability 返回中加入 backend started_at 或 git sha 会减少 stale-server 混淆。

## 建议移除或合并的工具

无

## 其他备注

负向 live 调用因后端未重启插入了测试经验，已删除；当前源码直接校验已确认 global user write 被拒绝。

## 当前工具热度快照

```json
[
  {
    "tool": "code_node",
    "calls": 118,
    "error": 0,
    "avg_duration_seconds": 0.14
  },
  {
    "tool": "lint",
    "calls": 114,
    "error": 0,
    "avg_duration_seconds": 0.016
  },
  {
    "tool": "code_explore",
    "calls": 57,
    "error": 0,
    "avg_duration_seconds": 0.304
  },
  {
    "tool": "sql",
    "calls": 50,
    "error": 0,
    "avg_duration_seconds": 0.033
  },
  {
    "tool": "worktree_guard",
    "calls": 38,
    "error": 0,
    "avg_duration_seconds": 0.031
  },
  {
    "tool": "code_impact",
    "calls": 31,
    "error": 0,
    "avg_duration_seconds": 0.136
  },
  {
    "tool": "db_schema",
    "calls": 29,
    "error": 0,
    "avg_duration_seconds": 0.034
  },
  {
    "tool": "probe",
    "calls": 27,
    "error": 0,
    "avg_duration_seconds": 0.562
  },
  {
    "tool": "plan_task",
    "calls": 26,
    "error": 0,
    "avg_duration_seconds": 0.006
  },
  {
    "tool": "routes",
    "calls": 26,
    "error": 0,
    "avg_duration_seconds": 0.047
  }
]
```
