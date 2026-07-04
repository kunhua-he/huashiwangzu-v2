---
name: "工具台反馈-20260704-102034-codex-desktop-launcher-fileops-r1-批量文件操作反馈收口：use-file-operations 形成 Ba"
type: "reference"
tags: [mcp-feedback, dev-toolkit]
agent: "codex-desktop-launcher-fileops-r1"
created: "2026-07-04T10:20:34.045951+00:00"
---

# MCP 使用反馈

## 任务

批量文件操作反馈收口：use-file-operations 形成 BatchOperationResult，区分全部成功/部分成功/全部失败并暴露失败明细。

## 顺畅度

- 评分：4/5
- 体感：整体顺畅，brief/plan_task/codegraph/finish_task 串起来能快速确认边界和影响面。

## 本次用到的工具

brief, plan_task, worktree_guard, code_explore, code_node, code_impact, finish_task, memory_write, mcp_feedback

## 卡点 / 不顺手的地方

多人并行时 worktree_guard 的开工基线很快过期，后续新增的其他 worker 改动需要手动补 baseline，容易让本轮边界报告看起来嘈杂。

## 缺少的工具 / 能力

无

## 升级建议

worktree_guard/finish_task 可支持“只判指定 allowed_prefix 的实际 diff，其他 dirty 自动标记为 concurrent/ignored”的模式，减少并行开发噪声。

## 建议移除或合并的工具

无

## 其他备注

本轮未触碰 launcher/app-registry/window-manager/shell/backend/modules 禁止范围。

## 当前工具热度快照

```json
[
  {
    "tool": "code_node",
    "calls": 75,
    "error": 0,
    "avg_duration_seconds": 0.142
  },
  {
    "tool": "code_explore",
    "calls": 51,
    "error": 0,
    "avg_duration_seconds": 0.353
  },
  {
    "tool": "call_capability",
    "calls": 43,
    "error": 0,
    "avg_duration_seconds": 0.305
  },
  {
    "tool": "worktree_guard",
    "calls": 36,
    "error": 0,
    "avg_duration_seconds": 0.029
  },
  {
    "tool": "sql",
    "calls": 33,
    "error": 3,
    "avg_duration_seconds": 0.031
  },
  {
    "tool": "brief",
    "calls": 29,
    "error": 0,
    "avg_duration_seconds": 0.744
  },
  {
    "tool": "code_impact",
    "calls": 29,
    "error": 0,
    "avg_duration_seconds": 0.13
  },
  {
    "tool": "run_test",
    "calls": 28,
    "error": 0,
    "avg_duration_seconds": 4.78
  },
  {
    "tool": "plan_task",
    "calls": 27,
    "error": 0,
    "avg_duration_seconds": 0.006
  },
  {
    "tool": "probe",
    "calls": 20,
    "error": 0,
    "avg_duration_seconds": 0.489
  }
]
```
