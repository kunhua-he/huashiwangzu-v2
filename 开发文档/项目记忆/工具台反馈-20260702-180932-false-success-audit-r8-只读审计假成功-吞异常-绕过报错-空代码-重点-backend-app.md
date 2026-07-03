---
name: "工具台反馈-20260702-180932-false-success-audit-r8-只读审计假成功/吞异常/绕过报错/空代码，重点 backend/app、"
type: "reference"
tags: [mcp-feedback, dev-toolkit]
agent: "false-success-audit-r8"
created: "2026-07-02T18:09:32.628213+00:00"
---

# MCP 使用反馈

## 任务

只读审计假成功/吞异常/绕过报错/空代码，重点 backend/app、modules、dev_toolkit dirty 链路。

## 顺畅度

- 评分：4/5
- 体感：整体顺畅，brief/worktree_guard 很快定位 dirty 范围，code_explore 可满足必经流程。

## 本次用到的工具

brief,plan_task,worktree_guard,code_explore,tail_log,finish_task,memory_write,mcp_feedback

## 卡点 / 不顺手的地方

code_explore 大范围自然语言查询噪声偏大且输出截断，专项审计仍需 rg+实读 diff 收敛。

## 缺少的工具 / 能力

希望增加 false-success 专项扫描工具：识别 ApiResponse(data=result) 内含 success/status/error、except pass、completed+failed payload、skipped soft failure，并自动按 dirty 文件排序。

## 升级建议

code_explore 可支持限定 changed files 与 pattern 查询，减少 unrelated symbols。

## 建议移除或合并的工具

无

## 其他备注

本次按要求未改代码；memory_write 自身产生项目记忆文件属流程留痕。

## 当前工具热度快照

```json
[
  {
    "tool": "code_node",
    "calls": 441,
    "error": 0,
    "avg_duration_seconds": 0.145
  },
  {
    "tool": "lint",
    "calls": 275,
    "error": 0,
    "avg_duration_seconds": 0.016
  },
  {
    "tool": "sql",
    "calls": 236,
    "error": 10,
    "avg_duration_seconds": 0.031
  },
  {
    "tool": "code_explore",
    "calls": 224,
    "error": 0,
    "avg_duration_seconds": 0.321
  },
  {
    "tool": "db_schema",
    "calls": 154,
    "error": 0,
    "avg_duration_seconds": 0.033
  },
  {
    "tool": "worktree_guard",
    "calls": 147,
    "error": 0,
    "avg_duration_seconds": 0.031
  },
  {
    "tool": "run_test",
    "calls": 140,
    "error": 0,
    "avg_duration_seconds": 2.758
  },
  {
    "tool": "code_impact",
    "calls": 136,
    "error": 0,
    "avg_duration_seconds": 0.139
  },
  {
    "tool": "probe",
    "calls": 116,
    "error": 0,
    "avg_duration_seconds": 0.498
  },
  {
    "tool": "plan_task",
    "calls": 101,
    "error": 0,
    "avg_duration_seconds": 0.007
  }
]
```
