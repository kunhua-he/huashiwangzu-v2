---
name: "工具台反馈-20260702-142303-codex-knowledge-audit-explorer-Knowledge 全链路升级只读审计"
type: "reference"
tags: [mcp-feedback, dev-toolkit]
agent: "codex-knowledge-audit-explorer"
created: "2026-07-02T14:23:03.991276+00:00"
---

# MCP 使用反馈

## 任务

Knowledge 全链路升级只读审计

## 顺畅度

- 评分：4/5
- 体感：整体顺畅，工具台对审计取证很有帮助。

## 本次用到的工具

brief,plan_task,worktree_guard,capabilities,routes,db_schema,code_explore,tail_log,sql,probe,call_capability,finish_task,memory_write

## 卡点 / 不顺手的地方

code_explore 大查询容易被无关前端/其他模块命中并截断，仍需要回退精确 rg/nl。worktree_guard 开始干净但后续出现其他来源 dirty，无法标记“非本 agent 变更”。

## 缺少的工具 / 能力

希望增加只读审计报告模板工具：自动汇总路由/能力/DB 状态/日志关键词/dirty 来源时间。

## 升级建议

code_explore 支持限定路径前缀和 exclude glob；sql 输出最好保留列名而不是 col0/col1。

## 建议移除或合并的工具

无

## 其他备注

无

## 当前工具热度快照

```json
[
  {
    "tool": "code_node",
    "calls": 182,
    "error": 0,
    "avg_duration_seconds": 0.139
  },
  {
    "tool": "lint",
    "calls": 146,
    "error": 0,
    "avg_duration_seconds": 0.016
  },
  {
    "tool": "sql",
    "calls": 139,
    "error": 5,
    "avg_duration_seconds": 0.031
  },
  {
    "tool": "code_explore",
    "calls": 102,
    "error": 0,
    "avg_duration_seconds": 0.303
  },
  {
    "tool": "worktree_guard",
    "calls": 54,
    "error": 0,
    "avg_duration_seconds": 0.029
  },
  {
    "tool": "probe",
    "calls": 49,
    "error": 0,
    "avg_duration_seconds": 0.492
  },
  {
    "tool": "db_schema",
    "calls": 45,
    "error": 0,
    "avg_duration_seconds": 0.033
  },
  {
    "tool": "code_impact",
    "calls": 43,
    "error": 0,
    "avg_duration_seconds": 0.133
  },
  {
    "tool": "routes",
    "calls": 40,
    "error": 0,
    "avg_duration_seconds": 0.058
  },
  {
    "tool": "plan_task",
    "calls": 38,
    "error": 0,
    "avg_duration_seconds": 0.008
  }
]
```
