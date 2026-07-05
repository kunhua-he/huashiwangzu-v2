---
name: "工具台反馈-20260705-070625-codex-拆分 dev_toolkit/release_gate.py 为兼容 C"
type: "reference"
tags: [mcp-feedback, dev-toolkit]
agent: "codex"
created: "2026-07-05T07:06:25.267474+00:00"
---

# MCP 使用反馈

## 任务

拆分 dev_toolkit/release_gate.py 为兼容 CLI 入口和 release_gate 子包，并运行 release gate 验收。

## 顺畅度

- 评分：4/5
- 体感：整体顺畅，codegraph 和工具台测试/lint 很有用。

## 本次用到的工具

brief, plan_task, worktree_guard, code_explore, code_node, code_impact, lint, run_test, finish_task, memory_write, mcp_feedback

## 卡点 / 不顺手的地方

lint 工具对目录参数 `dev_toolkit/release_gate` 报“文件不存在”，需要逐文件传参；并发共享工作区被其他任务切分支/写 frontend tests，导致 boundary/full gate 结果混入外部 dirty。

## 缺少的工具 / 能力

希望 mailbox_create_delivery_bundle 支持更细的 full gate 摘要字段和 blocked-but-delivered 状态模板。

## 升级建议

lint 可识别目录并递归传给 ruff；worktree_guard 如能记录开工 baseline token 并在 finish_task 直接传入会更稳。

## 建议移除或合并的工具

无

## 其他备注

full gate 真实运行，当前 BLOCKED 由外部 UI Playwright 失败导致；release_gate 拆分本身的 ruff/pytest/skip-ui gate 均通过。

## 当前工具热度快照

```json
[
  {
    "tool": "probe",
    "calls": 58,
    "error": 3,
    "avg_duration_seconds": 0.258
  },
  {
    "tool": "run_test",
    "calls": 52,
    "error": 0,
    "avg_duration_seconds": 2.741
  },
  {
    "tool": "code_node",
    "calls": 29,
    "error": 0,
    "avg_duration_seconds": 0.146
  },
  {
    "tool": "lint",
    "calls": 28,
    "error": 0,
    "avg_duration_seconds": 0.092
  },
  {
    "tool": "worktree_guard",
    "calls": 26,
    "error": 0,
    "avg_duration_seconds": 0.03
  },
  {
    "tool": "sql",
    "calls": 24,
    "error": 3,
    "avg_duration_seconds": 0.03
  },
  {
    "tool": "code_impact",
    "calls": 22,
    "error": 0,
    "avg_duration_seconds": 0.133
  },
  {
    "tool": "finish_task",
    "calls": 16,
    "error": 0,
    "avg_duration_seconds": 1.424
  },
  {
    "tool": "release_gate",
    "calls": 15,
    "error": 0,
    "avg_duration_seconds": 23.544
  },
  {
    "tool": "test_data_pollution_audit",
    "calls": 14,
    "error": 0,
    "avg_duration_seconds": 0.034
  }
]
```
