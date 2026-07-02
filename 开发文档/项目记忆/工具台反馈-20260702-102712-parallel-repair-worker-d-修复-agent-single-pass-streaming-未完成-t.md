---
name: "工具台反馈-20260702-102712-parallel-repair-worker-d-修复 Agent single-pass streaming 未完成 t"
type: "reference"
tags: [mcp-feedback, dev-toolkit]
agent: "parallel-repair-worker-d"
created: "2026-07-02T10:27:12.720252+00:00"
---

# MCP 使用反馈

## 任务

修复 Agent single-pass streaming 未完成 tool intent 的 error+break 回退并补测试

## 顺畅度

- 评分：4/5
- 体感：brief/plan_task/code_explore/run_test 流程顺畅，能快速定位到 _stream_until_tool_or_done。

## 本次用到的工具

brief, plan_task, worktree_guard, code_explore, code_node, code_impact, routes, capabilities, db_schema, lint, run_test, finish_task, memory_write

## 卡点 / 不顺手的地方

lint 工具 path 不支持逗号列表；run_test 对 modules/... 会在 backend cwd 下误解析，需要传 ../modules/...；finish_task module_key 无法表达 backend/tests 作为模块任务允许测试路径。

## 缺少的工具 / 能力

希望 finish_task 支持 allowed_prefixes，避免模块任务补 backend/tests 时产生边界噪声。

## 升级建议

让 run_test 对仓库根相对 paths 自动归一；lint 支持多路径或明确报错提示。

## 建议移除或合并的工具

无

## 其他备注

无

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
    "tool": "code_explore",
    "calls": 22,
    "error": 0,
    "avg_duration_seconds": 0.302
  },
  {
    "tool": "worktree_guard",
    "calls": 20,
    "error": 0,
    "avg_duration_seconds": 0.031
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
    "tool": "brief",
    "calls": 9,
    "error": 0,
    "avg_duration_seconds": 0.727
  },
  {
    "tool": "finish_task",
    "calls": 9,
    "error": 0,
    "avg_duration_seconds": 0.183
  },
  {
    "tool": "lint",
    "calls": 9,
    "error": 0,
    "avg_duration_seconds": 0.022
  },
  {
    "tool": "mcp_feedback",
    "calls": 9,
    "error": 0,
    "avg_duration_seconds": 0.012
  }
]
```
