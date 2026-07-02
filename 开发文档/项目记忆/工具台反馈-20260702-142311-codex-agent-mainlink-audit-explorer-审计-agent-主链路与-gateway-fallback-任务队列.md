---
name: "工具台反馈-20260702-142311-codex-agent-mainlink-audit-explorer-审计 Agent 主链路与 gateway/fallback/任务队列/"
type: "reference"
tags: [mcp-feedback, dev-toolkit]
agent: "codex-agent-mainlink-audit-explorer"
created: "2026-07-02T14:23:11.932460+00:00"
---

# MCP 使用反馈

## 任务

审计 Agent 主链路与 gateway/fallback/任务队列/capability 交互，只探查不改代码。

## 顺畅度

- 评分：4/5
- 体感：整体顺畅，CodeGraph 对主链路定位很快，项目工具台健康探针和 capabilities 很有用。

## 本次用到的工具

brief, plan_task, worktree_guard, code_explore, code_node, routes, capabilities, db_schema, probe, tail_log, finish_task, memory_write

## 卡点 / 不顺手的地方

code_node 的 offset/limit 参数未按预期返回后半段文件内容，只能回退 shell nl/sed 读取指定行。capabilities 全量输出很长，容易截断。

## 缺少的工具 / 能力

希望 code_node 支持稳定的 offset/limit 或按行号区间读取；capabilities 希望支持 action/filter 精确过滤。

## 升级建议

为审计类任务增加一个只读 grep preset，例如扫描模块间 import、直接表名访问、gateway_router 直接调用、SystemTaskQueue handler semantic failure。

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
