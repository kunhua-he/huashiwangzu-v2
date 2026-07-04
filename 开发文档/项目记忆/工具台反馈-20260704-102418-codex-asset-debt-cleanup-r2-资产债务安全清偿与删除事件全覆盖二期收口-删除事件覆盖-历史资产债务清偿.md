---
name: "工具台反馈-20260704-102418-codex-asset-debt-cleanup-r2-资产债务安全清偿与删除事件全覆盖二期收口：删除事件覆盖、历史资产债务清偿"
type: "reference"
tags: [mcp-feedback, dev-toolkit]
agent: "codex-asset-debt-cleanup-r2"
created: "2026-07-04T10:24:18.386030+00:00"
---

# MCP 使用反馈

## 任务

资产债务安全清偿与删除事件全覆盖二期收口：删除事件覆盖、历史资产债务清偿、release gate 资产项解除 BLOCKER。

## 顺畅度

- 评分：4/5
- 体感：整体顺畅，brief/plan_task/worktree_guard/lint/run_test/probe/call_capability/release_gate/finish_task 串起来能覆盖完整闭环。

## 本次用到的工具

brief, plan_task, worktree_guard, code_explore, lint, run_test, probe, call_capability, sql, release_gate, finish_task, memory_write, mcp_feedback

## 卡点 / 不顺手的地方

asset_lifecycle_tools 的 test_data_pollution_audit/cleanup 在工具搜索后没有作为直接 MCP 工具暴露，只能通过 Python 导入函数执行；release_gate 输出很长，dirty 文件 JSON 在结果里占比偏大。

## 缺少的工具 / 能力

希望直接暴露 test_data_pollution_audit 和 test_data_pollution_cleanup 两个工具；希望 release_gate 支持 max_bytes/selector 只返回 summary/context 中的关键字段。

## 升级建议

finish_task 可支持自动把当前工作树中不在 allowed_prefixes 的路径一键标为 baseline 候选并让 agent确认，减少长 baseline 手填。

## 建议移除或合并的工具

无

## 其他备注

二期收口报告已写入 开发文档/项目记忆/资产债务清偿主闭环二期收口.md。

## 当前工具热度快照

```json
[
  {
    "tool": "call_capability",
    "calls": 78,
    "error": 5,
    "avg_duration_seconds": 0.293
  },
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
    "tool": "worktree_guard",
    "calls": 37,
    "error": 0,
    "avg_duration_seconds": 0.029
  },
  {
    "tool": "run_test",
    "calls": 36,
    "error": 0,
    "avg_duration_seconds": 4.923
  },
  {
    "tool": "sql",
    "calls": 35,
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
    "tool": "plan_task",
    "calls": 27,
    "error": 0,
    "avg_duration_seconds": 0.006
  },
  {
    "tool": "probe",
    "calls": 26,
    "error": 0,
    "avg_duration_seconds": 0.58
  }
]
```
