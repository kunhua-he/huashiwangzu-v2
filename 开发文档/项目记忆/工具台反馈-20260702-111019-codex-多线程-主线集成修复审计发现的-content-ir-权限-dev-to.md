---
name: "工具台反馈-20260702-111019-codex-多线程/主线集成修复审计发现的 Content IR 权限、dev_to"
type: "reference"
tags: [mcp-feedback, dev-toolkit]
agent: "codex"
created: "2026-07-02T11:10:19.392022+00:00"
---

# MCP 使用反馈

## 任务

多线程/主线集成修复审计发现的 Content IR 权限、dev_toolkit SQL/release gate、Agent 策略/streaming、Knowledge 文件生命周期与 smoke 假绿。

## 顺畅度

- 评分：4/5
- 体感：整体顺畅，brief/plan_task/worktree_guard/run_test/release_gate/finish_task 串起来很好用。

## 本次用到的工具

brief, plan_task, worktree_guard, code_explore, run_test, release_gate, tail_log, finish_task, memory_write, mcp_feedback

## 卡点 / 不顺手的地方

release_gate MCP 工具进程疑似加载旧 server.py，脚本输出已是 PASS_WITH_DEBT 但工具顶层仍显示 success=true/verdict=PASS，容易误导；需重启 MCP 或让工具支持自检当前文件 hash/版本。

## 缺少的工具 / 能力

缺一个 restart/reload 当前项目工具台 MCP 的安全工具，或至少 expose server.py loaded version/hash 的诊断工具。

## 升级建议

release_gate/smoke_all MCP wrapper 应统一返回 raw_summary + wrapper_version，并在 PASS_WITH_DEBT 时 success=false、release_safe=true；工具台可提示“当前 MCP 进程代码版本可能旧于磁盘”。

## 建议移除或合并的工具

无。

## 其他备注

本次使用子代理做只读调用链确认，主线完成集成和验证。

## 当前工具热度快照

```json
[
  {
    "tool": "code_node",
    "calls": 71,
    "error": 0,
    "avg_duration_seconds": 0.139
  },
  {
    "tool": "lint",
    "calls": 39,
    "error": 0,
    "avg_duration_seconds": 0.017
  },
  {
    "tool": "code_explore",
    "calls": 37,
    "error": 0,
    "avg_duration_seconds": 0.303
  },
  {
    "tool": "worktree_guard",
    "calls": 29,
    "error": 0,
    "avg_duration_seconds": 0.032
  },
  {
    "tool": "code_impact",
    "calls": 20,
    "error": 0,
    "avg_duration_seconds": 0.134
  },
  {
    "tool": "plan_task",
    "calls": 18,
    "error": 0,
    "avg_duration_seconds": 0.003
  },
  {
    "tool": "probe",
    "calls": 17,
    "error": 0,
    "avg_duration_seconds": 0.57
  },
  {
    "tool": "brief",
    "calls": 16,
    "error": 0,
    "avg_duration_seconds": 0.735
  },
  {
    "tool": "db_schema",
    "calls": 14,
    "error": 0,
    "avg_duration_seconds": 0.033
  },
  {
    "tool": "memory_write",
    "calls": 13,
    "error": 0,
    "avg_duration_seconds": 0.545
  }
]
```
