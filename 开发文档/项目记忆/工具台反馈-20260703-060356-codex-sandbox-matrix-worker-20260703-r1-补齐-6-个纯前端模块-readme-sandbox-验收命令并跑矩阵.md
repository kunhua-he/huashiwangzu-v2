---
name: "工具台反馈-20260703-060356-codex-sandbox-matrix-worker-20260703-r1-补齐 6 个纯前端模块 README sandbox 验收命令并跑矩阵/"
type: "reference"
tags: [mcp-feedback, dev-toolkit]
agent: "codex-sandbox-matrix-worker-20260703-r1"
created: "2026-07-03T06:03:56.565137+00:00"
---

# MCP 使用反馈

## 任务

补齐 6 个纯前端模块 README sandbox 验收命令并跑矩阵/前端构建验证。

## 顺畅度

- 评分：4/5
- 体感：整体顺畅，brief/plan/worktree/matrix/finish/memory 都可用。

## 本次用到的工具

brief, plan_task, worktree_guard, code_explore, code_node, code_impact, module_sandbox_matrix, agent_board_heartbeat, finish_task, memory_write

## 卡点 / 不顺手的地方

agent_board_heartbeat 必须已有 task_id，两种合理 task_id 都返回 task not found，worker 无法自行发现或创建 board task。code_explore 对 dev_toolkit/module_sandbox_matrix.py 的自然语言查询先误命中 runtime modules 常量，需改用 code_node。

## 缺少的工具 / 能力

缺一个 agent_board 当前任务发现/创建工具，或 heartbeat 支持 upsert 当前 agent task。

## 升级建议

module_sandbox_matrix 可额外输出简短 summary-only 模式，方便最终报告 pass/fail/skip 计数而不返回超长 JSON。

## 建议移除或合并的工具

无

## 其他备注

并行工作区中收工时出现他人脏文件，worktree_guard 能清楚暴露风险。

## 当前工具热度快照

```json
[
  {
    "tool": "code_node",
    "calls": 558,
    "error": 0,
    "avg_duration_seconds": 0.145
  },
  {
    "tool": "lint",
    "calls": 402,
    "error": 0,
    "avg_duration_seconds": 0.017
  },
  {
    "tool": "code_explore",
    "calls": 283,
    "error": 0,
    "avg_duration_seconds": 0.324
  },
  {
    "tool": "sql",
    "calls": 270,
    "error": 13,
    "avg_duration_seconds": 0.031
  },
  {
    "tool": "worktree_guard",
    "calls": 213,
    "error": 0,
    "avg_duration_seconds": 0.031
  },
  {
    "tool": "run_test",
    "calls": 201,
    "error": 2,
    "avg_duration_seconds": 3.163
  },
  {
    "tool": "code_impact",
    "calls": 189,
    "error": 0,
    "avg_duration_seconds": 0.137
  },
  {
    "tool": "db_schema",
    "calls": 173,
    "error": 0,
    "avg_duration_seconds": 0.033
  },
  {
    "tool": "plan_task",
    "calls": 152,
    "error": 0,
    "avg_duration_seconds": 0.007
  },
  {
    "tool": "brief",
    "calls": 145,
    "error": 0,
    "avg_duration_seconds": 0.803
  }
]
```
