---
name: "工具台反馈-20260703-062118-codex-office-gen-worker-20260703-r1-office-gen 模块质量升级：Content IR 输入兼容、Ar"
type: "reference"
tags: [mcp-feedback, dev-toolkit]
agent: "codex-office-gen-worker-20260703-r1"
created: "2026-07-03T06:21:18.375769+00:00"
---

# MCP 使用反馈

## 任务

office-gen 模块质量升级：Content IR 输入兼容、Artifact/Content Package 状态边界、convert 权限路径防护、sandbox/README 验收补齐。

## 顺畅度

- 评分：4/5
- 体感：整体顺畅，brief/plan/worktree_guard/codegraph/lint/run_test/probe 串起来很清楚。

## 本次用到的工具

brief, plan_task, worktree_guard, code_explore, code_node, code_impact, routes, capabilities, db_schema, lint, run_test, probe, tail_log, finish_task, memory_write, agent_board_claim, agent_board_heartbeat

## 卡点 / 不顺手的地方

agent_board_claim 在同一 owner 已持有任务时会拒绝重复记录节点，只能用 heartbeat 追加；finish_task 在共享 dirty 工作区下会整体 success:false，需要人工区分本 agent 范围 diff。

## 缺少的工具 / 能力

希望有 agent_board_complete 或 finish_task 能支持 expected_shared_dirty=true / allowed_existing_dirty_snapshot，便于多 agent 场景下模块任务收尾不被他人 dirty 淹没。

## 升级建议

worktree_guard 可增加 baseline 参数：开工时记录外部 dirty，收工只判新增越界；finish_task 可显示 `git diff --name-only -- modules/{key}` 专栏。

## 建议移除或合并的工具

无。

## 其他备注

未运行写入型 live capability，避免共享库新增测试文件；无测试数据需要清理。

## 当前工具热度快照

```json
[
  {
    "tool": "code_node",
    "calls": 613,
    "error": 0,
    "avg_duration_seconds": 0.145
  },
  {
    "tool": "lint",
    "calls": 443,
    "error": 0,
    "avg_duration_seconds": 0.019
  },
  {
    "tool": "code_explore",
    "calls": 291,
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
    "calls": 225,
    "error": 2,
    "avg_duration_seconds": 3.276
  },
  {
    "tool": "worktree_guard",
    "calls": 224,
    "error": 0,
    "avg_duration_seconds": 0.031
  },
  {
    "tool": "code_impact",
    "calls": 207,
    "error": 0,
    "avg_duration_seconds": 0.137
  },
  {
    "tool": "db_schema",
    "calls": 184,
    "error": 0,
    "avg_duration_seconds": 0.033
  },
  {
    "tool": "probe",
    "calls": 164,
    "error": 2,
    "avg_duration_seconds": 0.47
  },
  {
    "tool": "plan_task",
    "calls": 157,
    "error": 0,
    "avg_duration_seconds": 0.007
  }
]
```
