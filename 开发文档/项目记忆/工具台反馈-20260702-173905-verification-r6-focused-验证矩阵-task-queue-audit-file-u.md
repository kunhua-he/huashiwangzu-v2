---
name: "工具台反馈-20260702-173905-verification-r6-focused 验证矩阵：task_queue_audit、file_u"
type: "reference"
tags: [mcp-feedback, dev-toolkit]
agent: "verification-r6"
created: "2026-07-02T17:39:05.923094+00:00"
---

# MCP 使用反馈

## 任务

focused 验证矩阵：task_queue_audit、file_upload_sessions、parser_resource_diagnostics、private_modules_lifecycle、dev_toolkit agent board/mcp entry、ruff、git diff --check；本轮只验证不改代码

## 顺畅度

- 评分：4/5
- 体感：单项 run_test、brief、worktree_guard 都顺畅，适合 verification agent 快速归档证据。

## 本次用到的工具

brief, plan_task, worktree_guard, run_test, finish_task, memory_write, mcp_feedback, codegraph CLI

## 卡点 / 不顺手的地方

finish_task 对混合 backend/tests 与 dev_toolkit 测试目标的路径归一化有问题：在仓库根执行时把 backend/tests 归成 tests/...，产生 no tests ran 的假失败。

## 缺少的工具 / 能力

希望 run_test/finish_task 支持一次性传结构化 target 列表，并保留每个 target 的 cwd/normalized_target，而不是混合路径时重新猜测。

## 升级建议

finish_task 可以接受 verification-only 模式，允许直接填入已完成单项测试结果，避免为了收工再次执行一个路径归一可能不同的合跑。另建议 worktree_guard 对 backend/data/.upload_sessions 这类运行时产物给出是否应清理的规则提示。

## 建议移除或合并的工具

无

## 其他备注

本轮发现 private module deactivate route 未摘除、upload session 测试 import 顺序、两个未跟踪 .part 文件。

## 当前工具热度快照

```json
[
  {
    "tool": "code_node",
    "calls": 412,
    "error": 0,
    "avg_duration_seconds": 0.145
  },
  {
    "tool": "lint",
    "calls": 271,
    "error": 0,
    "avg_duration_seconds": 0.016
  },
  {
    "tool": "code_explore",
    "calls": 211,
    "error": 0,
    "avg_duration_seconds": 0.318
  },
  {
    "tool": "sql",
    "calls": 208,
    "error": 8,
    "avg_duration_seconds": 0.031
  },
  {
    "tool": "worktree_guard",
    "calls": 141,
    "error": 0,
    "avg_duration_seconds": 0.031
  },
  {
    "tool": "run_test",
    "calls": 135,
    "error": 0,
    "avg_duration_seconds": 2.778
  },
  {
    "tool": "code_impact",
    "calls": 134,
    "error": 0,
    "avg_duration_seconds": 0.139
  },
  {
    "tool": "db_schema",
    "calls": 129,
    "error": 0,
    "avg_duration_seconds": 0.033
  },
  {
    "tool": "probe",
    "calls": 111,
    "error": 0,
    "avg_duration_seconds": 0.507
  },
  {
    "tool": "plan_task",
    "calls": 97,
    "error": 0,
    "avg_duration_seconds": 0.007
  }
]
```
