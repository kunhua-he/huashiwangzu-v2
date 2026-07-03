---
name: "工具台反馈-20260702-180940-reference-upgrade-scout-r7-参考源码调研 3-5 个底层/MCP/知识库/agent 工作流升级小链"
type: "reference"
tags: [mcp-feedback, dev-toolkit]
agent: "reference-upgrade-scout-r7"
created: "2026-07-02T18:09:40.571761+00:00"
---

# MCP 使用反馈

## 任务

参考源码调研 3-5 个底层/MCP/知识库/agent 工作流升级小链路

## 顺畅度

- 评分：4/5
- 体感：整体顺畅，brief/plan/worktree/code_explore/db_schema 能快速把参考源码建议映射到本项目文件。

## 本次用到的工具

brief, plan_task, worktree_guard, code_explore, tail_log, memory_search, capabilities, routes, db_schema, memory_write, mcp_feedback

## 卡点 / 不顺手的地方

tail_log 在本次只读调研中没有有效信息；reference_sources 不在 codegraph 索引内，只能用 shell rg/sed 手动读。

## 缺少的工具 / 能力

如果工具台能提供 reference_sources_catalog / reference_grep / reference_read 这类只读工具，会更利于统一留痕和避免大 rg 输出截断。

## 升级建议

可增加一个 reference_source_scan 工具：限定 /Users/hekunhua/Documents/Agent/reference_sources，支持列项目、按关键词 grep、按文件片段读取，并自动记录引用文件路径。

## 建议移除或合并的工具

无

## 其他备注

本轮未下载新源码，未改项目代码；仅按要求写入开工/完成记忆与 MCP 反馈。

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
    "calls": 236,
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
    "calls": 147,
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
    "calls": 116,
    "error": 0,
    "avg_duration_seconds": 0.498
  },
  {
    "tool": "plan_task",
    "calls": 101,
    "error": 0,
    "avg_duration_seconds": 0.007
  }
]
```
