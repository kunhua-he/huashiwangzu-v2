---
name: "工具台反馈-20260703-161931-codex-project-audit-current-state-只读审计当前项目为何进入怪圈，并整合 5 个子代理结论。"
type: "reference"
tags: [mcp-feedback, dev-toolkit]
agent: "codex-project-audit-current-state"
created: "2026-07-03T16:19:31.666258+00:00"
---

# MCP 使用反馈

## 任务

只读审计当前项目为何进入怪圈，并整合 5 个子代理结论。

## 顺畅度

- 评分：4/5
- 体感：工具台整体顺畅，尤其是 release_gate/sql/agent_board_snapshot 能快速定位带债绿灯问题。

## 本次用到的工具

brief,plan_task,worktree_guard,code_explore,probe,sql,release_gate,module_sandbox_matrix,capabilities,agent_board_snapshot,finish_task,memory_write,mcp_feedback

## 卡点 / 不顺手的地方

capabilities 全量输出过长；agent_board_snapshot 输出过长且包含截断/噪音；worktree_guard 在共享 dirty 工作区仍难以归因到具体 agent。

## 缺少的工具 / 能力

需要一个收敛审计工具，把 git dirty、agent_board、投递箱/收件箱、OpenCode jobs、项目记忆、release gate 汇成唯一终态；需要 touched-files/agent attribution。

## 升级建议

agent_board complete 增加 commit/verification/dirty_scope 字段；release_gate 默认不 skip UI 或明确改名 backend_gate；finish_task 支持按开工 baseline 自动只验本轮 delta；投递箱已交付任务自动归档。

## 建议移除或合并的工具

可合并重复的 memory_recent/brief 中项目记忆噪音展示，默认只显示未收口任务。

## 其他备注

本轮未改产品代码，未执行生产 apply。

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
    "calls": 538,
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
