---
name: "工具台反馈-20260702-144608-codex-dev-toolkit-repair-worker-修复项目工具台 MCP 标准发现入口与 server.py 组件化工具声"
type: "reference"
tags: [mcp-feedback, dev-toolkit]
agent: "codex-dev-toolkit-repair-worker"
created: "2026-07-02T14:46:08.691812+00:00"
---

# MCP 使用反馈

## 任务

修复项目工具台 MCP 标准发现入口与 server.py 组件化工具声明

## 顺畅度

- 评分：4/5
- 体感：整体顺畅，brief/plan/codegraph/worktree/finish 都可用，适合这类工具台维修。

## 本次用到的工具

brief, plan_task, worktree_guard, code_explore, code_node, code_impact, finish_task, memory_write, mcp_feedback

## 卡点 / 不顺手的地方

共享工作区中其他 agent 持续写入导致 worktree_guard 全局失败，需要人工区分本任务改动与并行改动；后端 venv 有 pytest 但无 mcp，系统 python3.14 有 mcp 但无 pytest，MCP 相关测试只能拆开验证。

## 缺少的工具 / 能力

缺一个“按本 agent 本轮编辑文件快照做边界检查”的工具，用于共享工作区下区分自己改动和他人改动。

## 升级建议

给 finish_task 增加 allowed_prefixes 参数；给 mcp_self_check 增加协议工具名合法性检查；提供一个 MCP stdio smoke helper，直接返回 initialize/tools-list 摘要。

## 建议移除或合并的工具

无

## 其他备注

本次已将旧中文别名从公开 tools/list 移除，但保留服务端兼容。

## 当前工具热度快照

```json
[
  {
    "tool": "code_node",
    "calls": 196,
    "error": 0,
    "avg_duration_seconds": 0.139
  },
  {
    "tool": "lint",
    "calls": 187,
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
    "calls": 119,
    "error": 0,
    "avg_duration_seconds": 0.301
  },
  {
    "tool": "worktree_guard",
    "calls": 65,
    "error": 0,
    "avg_duration_seconds": 0.029
  },
  {
    "tool": "code_impact",
    "calls": 58,
    "error": 0,
    "avg_duration_seconds": 0.131
  },
  {
    "tool": "db_schema",
    "calls": 51,
    "error": 0,
    "avg_duration_seconds": 0.033
  },
  {
    "tool": "probe",
    "calls": 51,
    "error": 0,
    "avg_duration_seconds": 0.486
  },
  {
    "tool": "run_test",
    "calls": 49,
    "error": 0,
    "avg_duration_seconds": 3.861
  },
  {
    "tool": "plan_task",
    "calls": 45,
    "error": 0,
    "avg_duration_seconds": 0.008
  }
]
```
