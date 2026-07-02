---
name: "工具台反馈-20260702-152235-codex-knowledge-lifecycle-worker-修复 knowledge pipeline 生命周期债治理链路：dry-"
type: "reference"
tags: [mcp-feedback, dev-toolkit]
agent: "codex-knowledge-lifecycle-worker"
created: "2026-07-02T15:22:35.501382+00:00"
---

# MCP 使用反馈

## 任务

修复 knowledge pipeline 生命周期债治理链路：dry-run 分类、受控 archive/retry apply、只读能力注册和 focused tests。

## 顺畅度

- 评分：4/5
- 体感：整体顺畅，工具台能快速给出项目背景、schema、能力和 focused test 结果。

## 本次用到的工具

brief, plan_task, worktree_guard, code_explore, db_schema, routes, capabilities, lint, run_test, probe, tail_log, finish_task, memory_write

## 卡点 / 不顺手的地方

finish_task 的 module_key 边界默认不允许任务指定的 backend/tests 文件，导致本次合法测试改动被标为出界；routes 工具读取活栈 OpenAPI，未重启时看不到新代码路由。

## 缺少的工具 / 能力

希望 worktree_guard/finish_task 支持传 allowed_prefixes 叠加 module_key；routes 可增加静态代码路由解析模式或提示当前数据来自活栈。

## 升级建议

finish_task 可以接受任务白名单文件；probe 大响应可提供 summary_only 或 json_path 提取，避免 dry-run items 大量刷屏。

## 建议移除或合并的工具

无

## 其他备注

没有重启后端，避免打断当前多 agent dirty 工作区；用本地导入检查补充验证了新 POST route。

## 当前工具热度快照

```json
[
  {
    "tool": "code_node",
    "calls": 202,
    "error": 0,
    "avg_duration_seconds": 0.14
  },
  {
    "tool": "lint",
    "calls": 190,
    "error": 0,
    "avg_duration_seconds": 0.016
  },
  {
    "tool": "sql",
    "calls": 153,
    "error": 7,
    "avg_duration_seconds": 0.031
  },
  {
    "tool": "code_explore",
    "calls": 132,
    "error": 0,
    "avg_duration_seconds": 0.305
  },
  {
    "tool": "worktree_guard",
    "calls": 71,
    "error": 0,
    "avg_duration_seconds": 0.029
  },
  {
    "tool": "code_impact",
    "calls": 64,
    "error": 0,
    "avg_duration_seconds": 0.131
  },
  {
    "tool": "run_test",
    "calls": 63,
    "error": 0,
    "avg_duration_seconds": 3.423
  },
  {
    "tool": "db_schema",
    "calls": 56,
    "error": 0,
    "avg_duration_seconds": 0.033
  },
  {
    "tool": "probe",
    "calls": 54,
    "error": 0,
    "avg_duration_seconds": 0.48
  },
  {
    "tool": "plan_task",
    "calls": 50,
    "error": 0,
    "avg_duration_seconds": 0.008
  }
]
```
