---
name: "工具台反馈-20260703-060929-codex-agent-module-worker-20260703-r1-Agent 模块深度质量升级：checkpoint schema 对齐、"
type: "reference"
tags: [mcp-feedback, dev-toolkit]
agent: "codex-agent-module-worker-20260703-r1"
created: "2026-07-03T06:09:29.087211+00:00"
---

# MCP 使用反馈

## 任务

Agent 模块深度质量升级：checkpoint schema 对齐、subagent 轨迹持久化、模型重复定义清理。

## 顺畅度

- 评分：3/5
- 体感：核心工具可用，code_explore/db_reverse_audit/run_test 对定位很有帮助，但收尾阶段受并行 dirty 和 run_test 归一化影响较大。

## 本次用到的工具

brief, plan_task, worktree_guard, code_explore, code_node, code_impact, routes, capabilities, db_schema, db_reverse_audit, lint, run_test, probe, call_capability, tail_log, finish_task, memory_write

## 卡点 / 不顺手的地方

agent_board_heartbeat 两次返回 task not found，无法按要求落节点心跳；finish_task 传多个 test_targets 时把 backend/tests/test_checkpointer.py 归一到 root cwd 组合运行，导致看到旧 schema 失败，但 run_test 单跑同一目标 cwd=backend 通过；全局并行 dirty 会让 module boundary 检查失败，难以表达“本 agent 只改了模块内文件”。

## 缺少的工具 / 能力

缺少“创建/查询当前 agent_board task id”的工具；缺少“按本会话实际触碰文件做边界检查”的工具。

## 升级建议

finish_task 的 test_targets 建议复用 run_test 对每个目标的单独 cwd 归一化，不要合并成一次 pytest；worktree_guard 可增加 since-start 快照或 agent-owned-files 参数；agent_board_heartbeat 可在 task 不存在时返回可用 task 列表或提供 auto_create=false/true 行为。

## 建议移除或合并的工具

无

## 其他备注

本次按要求调用了 memory_write；由于项目记忆写在 开发文档/项目记忆，会让全局边界检查出现模块外 dirty，但这是开工铁律要求的留痕。

## 当前工具热度快照

```json
[
  {
    "tool": "code_node",
    "calls": 586,
    "error": 0,
    "avg_duration_seconds": 0.145
  },
  {
    "tool": "lint",
    "calls": 428,
    "error": 0,
    "avg_duration_seconds": 0.017
  },
  {
    "tool": "code_explore",
    "calls": 286,
    "error": 0,
    "avg_duration_seconds": 0.325
  },
  {
    "tool": "sql",
    "calls": 271,
    "error": 13,
    "avg_duration_seconds": 0.031
  },
  {
    "tool": "run_test",
    "calls": 220,
    "error": 2,
    "avg_duration_seconds": 3.333
  },
  {
    "tool": "worktree_guard",
    "calls": 220,
    "error": 0,
    "avg_duration_seconds": 0.031
  },
  {
    "tool": "code_impact",
    "calls": 196,
    "error": 0,
    "avg_duration_seconds": 0.137
  },
  {
    "tool": "db_schema",
    "calls": 178,
    "error": 0,
    "avg_duration_seconds": 0.033
  },
  {
    "tool": "plan_task",
    "calls": 154,
    "error": 0,
    "avg_duration_seconds": 0.007
  },
  {
    "tool": "probe",
    "calls": 153,
    "error": 0,
    "avg_duration_seconds": 0.45
  }
]
```
