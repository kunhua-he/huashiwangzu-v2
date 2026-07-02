---
name: "工具台反馈-20260702-114018-W6-codex-Knowledge kb_pipeline 生命周期债分类 dry-ru"
type: "reference"
tags: [mcp-feedback, dev-toolkit]
agent: "W6-codex"
created: "2026-07-02T11:40:18.269799+00:00"
---

# MCP 使用反馈

## 任务

Knowledge kb_pipeline 生命周期债分类 dry-run、source missing/deleted skipped 语义、同文档入队去重

## 顺畅度

- 评分：4/5
- 体感：整体顺畅，brief/plan/worktree/codegraph/run_test 串起来能快速定位已有修复雏形。

## 本次用到的工具

brief,plan_task,worktree_guard,code_explore,code_node,code_impact,routes,capabilities,db_schema,sql,lint,run_test,probe,tail_log,finish_task,memory_write

## 卡点 / 不顺手的地方

finish_task 的模块边界只按 modules/{key} 判断，无法表达用户额外授权的 backend/tests/test_knowledge_pipeline_lifecycle.py，导致收工检查假红。

## 缺少的工具 / 能力

希望 finish_task/worktree_guard 支持 allowed_prefixes 与 module_key 合并，或支持任务级 test exception。

## 升级建议

code_node 对新 untracked Python 文件不可见时可以提示 fallback command，finish_task 可输出本次 touched 文件与全局 dirty 分离视图。

## 建议移除或合并的工具

无

## 其他备注

本次未清历史队列表，只新增 dry-run 分类能力。

## 当前工具热度快照

```json
[
  {
    "tool": "code_node",
    "calls": 115,
    "error": 0,
    "avg_duration_seconds": 0.139
  },
  {
    "tool": "lint",
    "calls": 81,
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
    "calls": 37,
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
    "calls": 28,
    "error": 0,
    "avg_duration_seconds": 0.033
  },
  {
    "tool": "plan_task",
    "calls": 26,
    "error": 0,
    "avg_duration_seconds": 0.006
  },
  {
    "tool": "probe",
    "calls": 26,
    "error": 0,
    "avg_duration_seconds": 0.571
  },
  {
    "tool": "routes",
    "calls": 26,
    "error": 0,
    "avg_duration_seconds": 0.047
  }
]
```
