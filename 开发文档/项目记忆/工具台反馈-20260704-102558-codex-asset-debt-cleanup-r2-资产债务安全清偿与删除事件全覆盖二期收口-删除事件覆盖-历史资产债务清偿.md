---
name: "工具台反馈-20260704-102558-codex-asset-debt-cleanup-r2-资产债务安全清偿与删除事件全覆盖二期收口：删除事件覆盖、历史资产债务清偿"
type: "reference"
tags: [mcp-feedback, dev-toolkit]
agent: "codex-asset-debt-cleanup-r2"
created: "2026-07-04T10:25:58.062844+00:00"
---

# MCP 使用反馈

## 任务

资产债务安全清偿与删除事件全覆盖二期收口：删除事件覆盖、历史资产债务清偿、测试污染清理与 release gate 验证。

## 顺畅度

- 评分：4/5
- 体感：整体顺畅，brief/plan/codegraph/probe/call_capability/run_test/lint/release gate 组合效率很好。

## 本次用到的工具

brief
plan_task
worktree_guard
code_explore
code_node
code_impact
probe
call_capability
sql
lint
run_test
tail_log
finish_task
memory_write
mcp_feedback

## 卡点 / 不顺手的地方

代码修改后 MCP server 进程内的 test_data_pollution 工具未热加载新 marker，需要用磁盘代码直接验证；finish_task 的 test_targets 混合 backend 相对路径和仓库根绝对路径时 cwd 选择不理想，导致一次 JWT_SECRET 收集误报。

## 缺少的工具 / 能力

希望工具台提供 reload_self/reload_tool 或明确提示工具实现代码已改但当前 MCP 进程未重载。

## 升级建议

finish_task 对 run_test 的多个 target 可复用 run_test 的逐目标归一化策略，避免混合路径时从仓库根直接 pytest backend 测试。

## 建议移除或合并的工具

无

## 其他备注

release_gate 已证明资产生命周期与测试污染不再 BLOCKER；当前 dirty 中有大量其他任务文件，工具台能清楚暴露边界。

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
    "calls": 38,
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
    "calls": 36,
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
