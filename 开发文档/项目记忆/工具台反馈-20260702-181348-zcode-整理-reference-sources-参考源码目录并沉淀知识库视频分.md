---
name: "工具台反馈-20260702-181348-zcode-整理 reference_sources 参考源码目录并沉淀知识库视频分"
type: "reference"
tags: [mcp-feedback, dev-toolkit]
agent: "zcode"
created: "2026-07-02T18:13:48.966197+00:00"
---

# MCP 使用反馈

## 任务

整理 reference_sources 参考源码目录并沉淀知识库视频分析体系详细方案

## 顺畅度

- 评分：4/5
- 体感：整体顺畅，brief/plan_task/worktree_guard/code_explore 能快速确认项目边界，子 agent 并行阅读参考源码效率高。

## 本次用到的工具

brief, plan_task, worktree_guard, code_explore, capabilities, db_schema, tail_log, finish_task, memory_write, mcp_feedback

## 卡点 / 不顺手的地方

worktree_guard 对仓库外 reference_sources 无法纳入边界与 diff；finish_task 也只能看到仓库内改动。

## 缺少的工具 / 能力

希望增加一个专门管理仓库外 reference_sources 的 inventory/clone/catalog 工具，能记录代理、remote、commit、分类和本次新增列表。

## 升级建议

为调研类任务增加自动 reference catalog 生成工具；为 finish_task 增加 external_artifacts 字段，便于记录仓库外产物。

## 建议移除或合并的工具

无

## 其他备注

本次通过 4780 代理下载多个开源项目，最终方案已写入 开发文档/03_模块开发文档/knowledge_video_analysis_system_plan.md。

## 当前工具热度快照

```json
[
  {
    "tool": "code_node",
    "calls": 441,
    "error": 0,
    "avg_duration_seconds": 0.145
  },
  {
    "tool": "lint",
    "calls": 275,
    "error": 0,
    "avg_duration_seconds": 0.016
  },
  {
    "tool": "sql",
    "calls": 238,
    "error": 10,
    "avg_duration_seconds": 0.031
  },
  {
    "tool": "code_explore",
    "calls": 224,
    "error": 0,
    "avg_duration_seconds": 0.321
  },
  {
    "tool": "db_schema",
    "calls": 154,
    "error": 0,
    "avg_duration_seconds": 0.033
  },
  {
    "tool": "worktree_guard",
    "calls": 148,
    "error": 0,
    "avg_duration_seconds": 0.031
  },
  {
    "tool": "run_test",
    "calls": 140,
    "error": 0,
    "avg_duration_seconds": 2.758
  },
  {
    "tool": "code_impact",
    "calls": 136,
    "error": 0,
    "avg_duration_seconds": 0.139
  },
  {
    "tool": "probe",
    "calls": 119,
    "error": 0,
    "avg_duration_seconds": 0.493
  },
  {
    "tool": "plan_task",
    "calls": 101,
    "error": 0,
    "avg_duration_seconds": 0.007
  }
]
```
