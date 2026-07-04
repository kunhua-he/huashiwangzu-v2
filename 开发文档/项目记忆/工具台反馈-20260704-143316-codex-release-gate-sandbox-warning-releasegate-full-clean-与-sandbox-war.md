---
name: "工具台反馈-20260704-143316-codex-release-gate-sandbox-warning-ReleaseGate Full Clean 与 Sandbox War"
type: "reference"
tags: [mcp-feedback, dev-toolkit]
agent: "codex-release-gate-sandbox-warning"
created: "2026-07-04T14:33:16.182534+00:00"
---

# MCP 使用反馈

## 任务

ReleaseGate Full Clean 与 Sandbox Warning 总门禁收口

## 顺畅度

- 评分：3/5
- 体感：主体工具可用，但 full gate 后 MCP stdio transport closed，需要组件级兜底收尾。

## 本次用到的工具

brief, plan_task, worktree_guard, code_explore, code_node, code_impact, lint, run_test, module_sandbox_matrix, release_gate, tool_job_submit, tool_job_status, memory_write, mcp_feedback, mailbox_create_delivery_bundle

## 卡点 / 不顺手的地方

tool_job_status/brief 在后台 full gate 过程中返回 Transport closed；状态只能改用日志和进程树观察。

## 缺少的工具 / 能力

希望 tool_job_status 能在 MCP transport 重启后从状态文件恢复；或者提供 shell CLI 等价命令。

## 升级建议

后台 job 日志最好用 unbuffered Python 或实时 tail，release_gate 长任务当前日志在运行中几乎不刷新。

## 建议移除或合并的工具

无

## 其他备注

MCP stdio 在 full release_gate 后 tool_job_status/brief 返回 Transport closed；已用同一 dev_toolkit 组件函数直接写 memory/feedback/mailbox 五件套。建议后台 job runner 在长任务结束后更稳地刷新 status/output，或给 tool_job_status 一个独立轻量恢复通道。

## 当前工具热度快照

```json
[
  {
    "tool": "run_test",
    "calls": 33,
    "error": 0,
    "avg_duration_seconds": 2.222
  },
  {
    "tool": "code_node",
    "calls": 15,
    "error": 0,
    "avg_duration_seconds": 0.147
  },
  {
    "tool": "probe",
    "calls": 15,
    "error": 3,
    "avg_duration_seconds": 0.225
  },
  {
    "tool": "lint",
    "calls": 14,
    "error": 0,
    "avg_duration_seconds": 0.067
  },
  {
    "tool": "code_impact",
    "calls": 11,
    "error": 0,
    "avg_duration_seconds": 0.134
  },
  {
    "tool": "worktree_guard",
    "calls": 10,
    "error": 0,
    "avg_duration_seconds": 0.03
  },
  {
    "tool": "finish_task",
    "calls": 8,
    "error": 0,
    "avg_duration_seconds": 0.375
  },
  {
    "tool": "capabilities",
    "calls": 6,
    "error": 0,
    "avg_duration_seconds": 0.001
  },
  {
    "tool": "tail_log",
    "calls": 4,
    "error": 0,
    "avg_duration_seconds": 0.006
  },
  {
    "tool": "tool_job_notifications",
    "calls": 3,
    "error": 0,
    "avg_duration_seconds": 0.0
  }
]
```
