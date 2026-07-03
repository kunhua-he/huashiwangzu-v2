---
name: "工具台反馈-20260703-161821-codex-conductor-r6-R6 第二阶段主会话收口：集成知识库批量治理、parser defect"
type: "reference"
tags: [mcp-feedback, dev-toolkit]
agent: "codex-conductor-r6"
created: "2026-07-03T16:18:21.098167+00:00"
---

# MCP 使用反馈

## 任务

R6 第二阶段主会话收口：集成知识库批量治理、parser defect、media-intelligence 本地事实层、agent board conductor、UI gate 红项和算法研究报告。

## 顺畅度

- 评分：4/5
- 体感：整体可用，brief/plan/worktree_guard/codegraph/lint/run_test/probe/memory_write 帮助很大。

## 本次用到的工具

brief, plan_task, worktree_guard, code_explore, code_impact, lint, run_test, probe, call_capability, routes, tail_log, agent_board_snapshot, memory_write, mcp_feedback

## 卡点 / 不顺手的地方

多线程并发时 worktree_guard/finish_task 会被其他 worker dirty 干扰；MCP server 对新加工具字段需要重启才反映；UI gate 失败后清理状态需要手工核查。

## 缺少的工具 / 能力

希望有一个标准 conductor_finish 工具：聚合子代理终态、dirty 分组、测试矩阵、生产 apply 待确认清单、自动生成 commit body。

## 升级建议

agent_board_snapshot 的 conductor 区块已新增，后续可继续接入 subagent id、thread id、commit/stage 状态；probe 可以内置常见测试数据清理检查。

## 建议移除或合并的工具

无

## 其他备注

用户要求本批先停下重梳理，因此未执行 knowledge 60 条生产 apply，只保留 dry-run 证据和待确认命令。

## 当前工具热度快照

```json
[
  {
    "tool": "code_node",
    "calls": 1211,
    "error": 0,
    "avg_duration_seconds": 0.144
  },
  {
    "tool": "lint",
    "calls": 645,
    "error": 0,
    "avg_duration_seconds": 0.031
  },
  {
    "tool": "probe",
    "calls": 537,
    "error": 8,
    "avg_duration_seconds": 0.449
  },
  {
    "tool": "sql",
    "calls": 525,
    "error": 28,
    "avg_duration_seconds": 0.03
  },
  {
    "tool": "code_explore",
    "calls": 501,
    "error": 0,
    "avg_duration_seconds": 0.326
  },
  {
    "tool": "call_capability",
    "calls": 495,
    "error": 17,
    "avg_duration_seconds": 0.684
  },
  {
    "tool": "run_test",
    "calls": 444,
    "error": 2,
    "avg_duration_seconds": 3.873
  },
  {
    "tool": "code_impact",
    "calls": 428,
    "error": 0,
    "avg_duration_seconds": 0.134
  },
  {
    "tool": "worktree_guard",
    "calls": 414,
    "error": 0,
    "avg_duration_seconds": 0.03
  },
  {
    "tool": "db_schema",
    "calls": 358,
    "error": 0,
    "avg_duration_seconds": 0.033
  }
]
```
