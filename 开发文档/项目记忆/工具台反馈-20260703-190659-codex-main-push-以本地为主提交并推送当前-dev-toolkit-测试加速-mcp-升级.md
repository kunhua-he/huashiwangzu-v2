---
name: "工具台反馈-20260703-190659-codex-main-push-以本地为主提交并推送当前 dev_toolkit 测试加速/MCP 升级"
type: "reference"
tags: [mcp-feedback, dev-toolkit]
agent: "codex-main-push"
created: "2026-07-03T19:06:59.321273+00:00"
---

# MCP 使用反馈

## 任务

以本地为主提交并推送当前 dev_toolkit 测试加速/MCP 升级到 GitHub main

## 顺畅度

- 评分：4/5
- 体感：整体顺畅，tool_job_submit/status 可以把 preflight 和自测并行化，适合推送前快速收口。

## 本次用到的工具

worktree_guard, lint, run_test, tool_job_submit, tool_job_status, memory_write, mcp_feedback

## 卡点 / 不顺手的地方

tool_search 未加载前只看到 tool_job_submit，容易误把 status 查询做成 submit；需要更醒目的后台 job 状态工具发现提示。

## 缺少的工具 / 能力

希望 tool_job_submit 返回里直接给下一步 tool_job_status 的可点击/可调用提示，减少误操作。

## 升级建议

后台 job 工具可增加 submit_and_wait 简化短任务；或者在 submit 返回中附带状态查询模板。

## 建议移除或合并的工具

无

## 其他备注

本轮 push 前误触发了两个额外短 job，均成功完成，无副作用。

## 当前工具热度快照

```json
[
  {
    "tool": "code_node",
    "calls": 1323,
    "error": 0,
    "avg_duration_seconds": 0.144
  },
  {
    "tool": "lint",
    "calls": 664,
    "error": 0,
    "avg_duration_seconds": 0.031
  },
  {
    "tool": "probe",
    "calls": 575,
    "error": 8,
    "avg_duration_seconds": 0.448
  },
  {
    "tool": "code_explore",
    "calls": 572,
    "error": 0,
    "avg_duration_seconds": 0.326
  },
  {
    "tool": "sql",
    "calls": 566,
    "error": 35,
    "avg_duration_seconds": 0.031
  },
  {
    "tool": "call_capability",
    "calls": 499,
    "error": 17,
    "avg_duration_seconds": 0.681
  },
  {
    "tool": "worktree_guard",
    "calls": 480,
    "error": 0,
    "avg_duration_seconds": 0.03
  },
  {
    "tool": "run_test",
    "calls": 473,
    "error": 3,
    "avg_duration_seconds": 4.414
  },
  {
    "tool": "code_impact",
    "calls": 468,
    "error": 0,
    "avg_duration_seconds": 0.134
  },
  {
    "tool": "db_schema",
    "calls": 371,
    "error": 0,
    "avg_duration_seconds": 0.033
  }
]
```
