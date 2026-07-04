---
name: "工具台反馈-20260704-101714-codex-asset-lifecycle-closure-r1-资产生命周期总收口与测试污染门禁：补齐 Knowledge/Conten"
type: "reference"
tags: [mcp-feedback, dev-toolkit]
agent: "codex-asset-lifecycle-closure-r1"
created: "2026-07-04T10:17:14.134366+00:00"
---

# MCP 使用反馈

## 任务

资产生命周期总收口与测试污染门禁：补齐 Knowledge/ContentPackage 生命周期治理、文件/回收站/desktop-tools 删除事件闭环、测试污染清理和 release gate 资产项，并完成历史数据清偿。

## 顺畅度

- 评分：4/5
- 体感：整体顺畅，brief/plan_task/code_explore/sql/capability/release_gate/run_test 串起来能支撑完整闭环。

## 本次用到的工具

brief, plan_task, worktree_guard, code_explore, db_schema, capabilities, routes, call_capability, probe, sql, lint, run_test, tool_job_submit, tool_job_status, release_gate, tail_log, finish_task, memory_write

## 卡点 / 不顺手的地方

finish_task 的 test_targets 从仓库根合跑 backend 测试时缺 backend/.env 环境，产生与已分组 run_test 不一致的收集错误；工作区并行出现 unrelated frontend 变更时，边界报告需要手动用 baseline_paths 说明。

## 缺少的工具 / 能力

希望 finish_task 支持只引用已跑 timing_data 而不自动重跑 test_targets，或支持按 backend cwd 分组跑混合 backend/dev_toolkit/module 测试。

## 升级建议

release_gate/finish_task 可在 dirty 样本里标记 baseline/unrelated 更清晰；asset lifecycle cleanup 可以提供 MCP 直接工具热加载状态提示，避免改完 dev_toolkit 后需要用 Python 直调。

## 建议移除或合并的工具

无

## 其他备注

本轮真实清理了历史测试污染和生命周期债务；清理动作均经过 dry-run、错误 confirm、真实 confirm 验证。

## 当前工具热度快照

```json
[
  {
    "tool": "code_node",
    "calls": 75,
    "error": 0,
    "avg_duration_seconds": 0.142
  },
  {
    "tool": "code_explore",
    "calls": 49,
    "error": 0,
    "avg_duration_seconds": 0.353
  },
  {
    "tool": "call_capability",
    "calls": 35,
    "error": 0,
    "avg_duration_seconds": 0.314
  },
  {
    "tool": "worktree_guard",
    "calls": 31,
    "error": 0,
    "avg_duration_seconds": 0.028
  },
  {
    "tool": "code_impact",
    "calls": 28,
    "error": 0,
    "avg_duration_seconds": 0.13
  },
  {
    "tool": "sql",
    "calls": 28,
    "error": 2,
    "avg_duration_seconds": 0.031
  },
  {
    "tool": "brief",
    "calls": 26,
    "error": 0,
    "avg_duration_seconds": 0.745
  },
  {
    "tool": "plan_task",
    "calls": 25,
    "error": 0,
    "avg_duration_seconds": 0.006
  },
  {
    "tool": "run_test",
    "calls": 22,
    "error": 0,
    "avg_duration_seconds": 5.072
  },
  {
    "tool": "probe",
    "calls": 19,
    "error": 0,
    "avg_duration_seconds": 0.5
  }
]
```
