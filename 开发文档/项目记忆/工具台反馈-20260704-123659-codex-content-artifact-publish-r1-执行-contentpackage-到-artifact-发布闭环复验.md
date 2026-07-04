---
name: "工具台反馈-20260704-123659-codex-content-artifact-publish-r1-执行 ContentPackage 到 Artifact 发布闭环复验，"
type: "reference"
tags: [mcp-feedback, dev-toolkit]
agent: "codex-content-artifact-publish-r1"
created: "2026-07-04T12:36:59.750559+00:00"
---

# MCP 使用反馈

## 任务

执行 ContentPackage 到 Artifact 发布闭环复验，并补强 content:publish 非 owner 权限负例测试。

## 顺畅度

- 评分：4/5
- 体感：整体顺畅，CodeGraph 和工具台很快确认现有闭环，finish_task 合跑测试也有用。

## 本次用到的工具

brief, plan_task, worktree_guard, code_explore, code_node, code_impact, db_schema, probe, call_capability, sql, finish_task, memory_write, mcp_feedback

## 卡点 / 不顺手的地方

finish_task 的 lint_paths 不接受目录路径，而执行信里的 ruff 命令常使用目录；第一次收工因此误报失败。

## 缺少的工具 / 能力

无。

## 升级建议

finish_task 可支持目录 lint，或在报错时提示改成具体 Python 文件/自动展开目录。

## 建议移除或合并的工具

无。

## 其他备注

本轮还用两个只读子代理做旁路审计，并按建议补了权限负例。

## 当前工具热度快照

```json
[
  {
    "tool": "code_node",
    "calls": 347,
    "error": 0,
    "avg_duration_seconds": 0.141
  },
  {
    "tool": "code_explore",
    "calls": 209,
    "error": 0,
    "avg_duration_seconds": 0.336
  },
  {
    "tool": "probe",
    "calls": 153,
    "error": 4,
    "avg_duration_seconds": 0.321
  },
  {
    "tool": "worktree_guard",
    "calls": 143,
    "error": 0,
    "avg_duration_seconds": 0.03
  },
  {
    "tool": "brief",
    "calls": 111,
    "error": 0,
    "avg_duration_seconds": 0.755
  },
  {
    "tool": "plan_task",
    "calls": 110,
    "error": 0,
    "avg_duration_seconds": 0.005
  },
  {
    "tool": "sql",
    "calls": 108,
    "error": 4,
    "avg_duration_seconds": 0.03
  },
  {
    "tool": "call_capability",
    "calls": 106,
    "error": 5,
    "avg_duration_seconds": 0.291
  },
  {
    "tool": "code_impact",
    "calls": 104,
    "error": 0,
    "avg_duration_seconds": 0.129
  },
  {
    "tool": "finish_task",
    "calls": 72,
    "error": 0,
    "avg_duration_seconds": 1.932
  }
]
```
