---
name: "工具台反馈-20260702-145908-codex-test-release-gate-worker-修复测试/发布门禁假绿：sandbox 矩阵纳入前端 build，san"
type: "reference"
tags: [mcp-feedback, dev-toolkit]
agent: "codex-test-release-gate-worker"
created: "2026-07-02T14:59:08.548775+00:00"
---

# MCP 使用反馈

## 任务

修复测试/发布门禁假绿：sandbox 矩阵纳入前端 build，sandbox 断言不再吞错，smoke 队列基线前移，release_gate 增加 completed-but-result-failed 语义检查。

## 顺畅度

- 评分：4/5
- 体感：整体顺畅，CodeGraph/finish_task 对影响面和验收留痕很有帮助。

## 本次用到的工具

brief, plan_task, worktree_guard, code_explore, code_node, code_impact, finish_task, memory_write, mcp_feedback, probe

## 卡点 / 不顺手的地方

lint 工具一次只接受单路径，多个文件需要改用 shell ruff；finish_task 无 allowed_prefixes 参数，混合 worker dirty 场景下边界报告噪声较大。

## 缺少的工具 / 能力

希望 finish_task 支持 allowed_prefixes；希望 module_sandbox_matrix 能输出精简失败摘要模式，避免 JSON 太长。

## 升级建议

给 dev_toolkit 增加 multi-path lint 包装；给 sandbox matrix 增加 --summary-json 或 --failures-only，方便 release gate 和人工阅读。

## 建议移除或合并的工具

无

## 其他备注

本节点暴露了 13 个 frontend sandbox build blocker，属于门禁变严后的真实红项，后续应专项修 sandbox 前端构建依赖/配置。

## 当前工具热度快照

```json
[
  {
    "tool": "code_node",
    "calls": 196,
    "error": 0,
    "avg_duration_seconds": 0.139
  },
  {
    "tool": "lint",
    "calls": 188,
    "error": 0,
    "avg_duration_seconds": 0.016
  },
  {
    "tool": "sql",
    "calls": 139,
    "error": 5,
    "avg_duration_seconds": 0.031
  },
  {
    "tool": "code_explore",
    "calls": 119,
    "error": 0,
    "avg_duration_seconds": 0.301
  },
  {
    "tool": "worktree_guard",
    "calls": 65,
    "error": 0,
    "avg_duration_seconds": 0.029
  },
  {
    "tool": "code_impact",
    "calls": 58,
    "error": 0,
    "avg_duration_seconds": 0.131
  },
  {
    "tool": "probe",
    "calls": 52,
    "error": 0,
    "avg_duration_seconds": 0.482
  },
  {
    "tool": "run_test",
    "calls": 52,
    "error": 0,
    "avg_duration_seconds": 3.762
  },
  {
    "tool": "db_schema",
    "calls": 51,
    "error": 0,
    "avg_duration_seconds": 0.033
  },
  {
    "tool": "plan_task",
    "calls": 45,
    "error": 0,
    "avg_duration_seconds": 0.008
  }
]
```
