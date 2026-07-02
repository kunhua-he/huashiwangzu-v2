---
name: "工具台反馈-20260702-160106-gateway-fallback-worker-审计并加固模型网关云端失败自动降级本地模型链路"
type: "reference"
tags: [mcp-feedback, dev-toolkit]
agent: "gateway-fallback-worker"
created: "2026-07-02T16:01:06.342648+00:00"
---

# MCP 使用反馈

## 任务

审计并加固模型网关云端失败自动降级本地模型链路

## 顺畅度

- 评分：4/5
- 体感：整体顺畅；stdio MCP 实际使用逐行 JSON，不是 Content-Length 帧，手动客户端第一次连接卡住。

## 本次用到的工具

brief, plan_task, worktree_guard, code_explore, code_impact, routes, lint, run_test, probe, tail_log, finish_task, memory_write

## 卡点 / 不顺手的地方

当前会话未原生暴露项目工具台 MCP，需要手写 JSON-RPC 客户端；worktree_guard 在多人 dirty worktree 下会整体 success=false，但仍能提供边界信息。

## 缺少的工具 / 能力

希望 Codex 运行环境能直接暴露项目工具台 MCP 工具，或提供 mcp_call 简易命令。

## 升级建议

dev_toolkit README 可明确 stdio transport 是 newline-delimited JSON；worktree_guard 可增加 only_prefixes 或 baseline 参数，便于多人并行时只检查本任务范围。

## 建议移除或合并的工具

暂无。

## 其他备注

无

## 当前工具热度快照

```json
[
  {
    "tool": "code_node",
    "calls": 287,
    "error": 0,
    "avg_duration_seconds": 0.145
  },
  {
    "tool": "lint",
    "calls": 215,
    "error": 0,
    "avg_duration_seconds": 0.017
  },
  {
    "tool": "sql",
    "calls": 159,
    "error": 7,
    "avg_duration_seconds": 0.03
  },
  {
    "tool": "code_explore",
    "calls": 149,
    "error": 0,
    "avg_duration_seconds": 0.309
  },
  {
    "tool": "code_impact",
    "calls": 94,
    "error": 0,
    "avg_duration_seconds": 0.139
  },
  {
    "tool": "worktree_guard",
    "calls": 88,
    "error": 0,
    "avg_duration_seconds": 0.03
  },
  {
    "tool": "db_schema",
    "calls": 76,
    "error": 0,
    "avg_duration_seconds": 0.034
  },
  {
    "tool": "run_test",
    "calls": 75,
    "error": 0,
    "avg_duration_seconds": 3.05
  },
  {
    "tool": "plan_task",
    "calls": 62,
    "error": 0,
    "avg_duration_seconds": 0.007
  },
  {
    "tool": "probe",
    "calls": 62,
    "error": 0,
    "avg_duration_seconds": 0.491
  }
]
```
