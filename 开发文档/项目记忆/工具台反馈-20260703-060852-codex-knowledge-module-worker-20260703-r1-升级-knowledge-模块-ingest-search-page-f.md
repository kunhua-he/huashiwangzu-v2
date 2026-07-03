---
name: "工具台反馈-20260703-060852-codex-knowledge-module-worker-20260703-r1-升级 knowledge 模块 ingest/search/page f"
type: "reference"
tags: [mcp-feedback, dev-toolkit]
agent: "codex-knowledge-module-worker-20260703-r1"
created: "2026-07-03T06:08:52.486485+00:00"
---

# MCP 使用反馈

## 任务

升级 knowledge 模块 ingest/search/page fusion/entity graph/prompt_utils/LLM 慢调用诊断与进度展示主链路质量，避免源文件缺失、LLM 空 fallback、graph 统计空表导致假成功或假未完成。

## 顺畅度

- 评分：3/5
- 体感：主流程工具可用，但收工与心跳在多 agent 脏工作树下体验不够顺。

## 本次用到的工具

brief, plan_task, worktree_guard, code_explore/codegraph CLI, probe, call_capability, finish_task, memory_write, mcp_feedback, agent_board_heartbeat

## 卡点 / 不顺手的地方

agent_board_heartbeat 多次返回 task not found，无法按节点落盘；finish_task 只按全仓 dirty 做模块边界失败，无法区分本 agent 改动与其他 agent 已存在改动。

## 缺少的工具 / 能力

需要一个按 paths 或 git diff base 只检查当前模块实际改动的 finish_task 模式，并允许记录已知外部 dirty 白名单。

## 升级建议

agent_board_heartbeat 可在 task not found 时返回可用 task 列表或允许按 agent 自动创建/绑定；finish_task 的 module_key 边界检查建议支持传入 ignore_existing_dirty=true 或 baseline 快照。

## 建议移除或合并的工具

无

## 其他备注

本次 memory_write 成功写入 开发文档/项目记忆/knowledge-主链路质量升级-2026-07-03.md。

## 当前工具热度快照

```json
[
  {
    "tool": "code_node",
    "calls": 576,
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
    "calls": 285,
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
    "calls": 195,
    "error": 0,
    "avg_duration_seconds": 0.138
  },
  {
    "tool": "db_schema",
    "calls": 174,
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
