---
name: "工具台反馈-20260703-093238-codex-conductor-sweep-20260703-r2-web-tools r2 network path hardening "
type: "reference"
tags: [mcp-feedback, dev-toolkit]
agent: "codex-conductor-sweep-20260703-r2"
created: "2026-07-03T09:32:38.465331+00:00"
---

# MCP 使用反馈

## 任务

web-tools r2 network path hardening and runtime upload ignore cleanup

## 顺畅度

- 评分：4/5
- 体感：工具台验证顺畅，call_capability 能直接确认 SSRF 与真实公网 fetch。

## 本次用到的工具

code_node, lint, run_test, probe, call_capability, tail_log, memory_write, mcp_feedback

## 卡点 / 不顺手的地方

lint 工具对非 Python 文件 .gitignore 不适用，需要主会话记住只传 Python 文件。

## 缺少的工具 / 能力

希望 lint 工具自动跳过非 Python 文件或给出更友好的提示。

## 升级建议

增加专门的 gitignore/check-ignore 验证工具，适合运行时产物治理。

## 建议移除或合并的工具

无

## 其他备注

已按用户建议放出 3 个只读流程审计代理，主会话保留验收和提交职责。

## 当前工具热度快照

```json
[
  {
    "tool": "code_node",
    "calls": 921,
    "error": 0,
    "avg_duration_seconds": 0.146
  },
  {
    "tool": "lint",
    "calls": 567,
    "error": 0,
    "avg_duration_seconds": 0.027
  },
  {
    "tool": "call_capability",
    "calls": 387,
    "error": 17,
    "avg_duration_seconds": 0.788
  },
  {
    "tool": "code_explore",
    "calls": 380,
    "error": 0,
    "avg_duration_seconds": 0.329
  },
  {
    "tool": "probe",
    "calls": 335,
    "error": 3,
    "avg_duration_seconds": 0.466
  },
  {
    "tool": "code_impact",
    "calls": 331,
    "error": 0,
    "avg_duration_seconds": 0.136
  },
  {
    "tool": "sql",
    "calls": 331,
    "error": 15,
    "avg_duration_seconds": 0.031
  },
  {
    "tool": "run_test",
    "calls": 322,
    "error": 2,
    "avg_duration_seconds": 3.316
  },
  {
    "tool": "worktree_guard",
    "calls": 313,
    "error": 0,
    "avg_duration_seconds": 0.031
  },
  {
    "tool": "db_schema",
    "calls": 256,
    "error": 0,
    "avg_duration_seconds": 0.033
  }
]
```
