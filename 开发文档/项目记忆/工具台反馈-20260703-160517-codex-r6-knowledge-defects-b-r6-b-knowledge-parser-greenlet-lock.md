---
name: "工具台反馈-20260703-160517-codex-r6-knowledge-defects-b-R6-B knowledge parser/greenlet/lock/"
type: "reference"
tags: [mcp-feedback, dev-toolkit]
agent: "codex-r6-knowledge-defects-b"
created: "2026-07-03T16:05:17.294584+00:00"
---

# MCP 使用反馈

## 任务

R6-B knowledge parser/greenlet/lock/retry 代码缺陷专项：修复 parse 入口快照访问和 stale parsing 锁安全释放，补测试并做活系统 debt 分类验证。

## 顺畅度

- 评分：4/5
- 体感：整体顺畅，brief/plan/worktree_guard/codegraph/finish_task 串起来能快速建立证据链。

## 本次用到的工具

brief, plan_task, worktree_guard, code_explore, code_node, code_impact, routes, capabilities, db_schema, sql, lint, run_test, probe, call_capability, finish_task, memory_write

## 卡点 / 不顺手的地方

并行 worker 改动导致 worktree_guard/finish_task 标红；工具能列出 dirty，但无法区分本 agent 实际触碰文件与并发改动。

## 缺少的工具 / 能力

希望有按本进程写入记录或 mtime/agent attribution 的 dirty 分组，帮助多 worker 场景下做边界验收。

## 升级建议

finish_task 可接受“本轮实际修改文件”参数并与全局 dirty 分开报告；call_capability/probe selector 可以提示 envelope 深度示例。

## 建议移除或合并的工具

无

## 其他备注

CodeGraph 对 parse_and_index_document 定位很快；live debt 分类 selector 第一次写浅后工具给了 warning，重试即可。

## 当前工具热度快照

```json
[
  {
    "tool": "code_node",
    "calls": 1197,
    "error": 0,
    "avg_duration_seconds": 0.144
  },
  {
    "tool": "lint",
    "calls": 639,
    "error": 0,
    "avg_duration_seconds": 0.03
  },
  {
    "tool": "sql",
    "calls": 515,
    "error": 25,
    "avg_duration_seconds": 0.031
  },
  {
    "tool": "probe",
    "calls": 503,
    "error": 6,
    "avg_duration_seconds": 0.444
  },
  {
    "tool": "code_explore",
    "calls": 488,
    "error": 0,
    "avg_duration_seconds": 0.326
  },
  {
    "tool": "call_capability",
    "calls": 475,
    "error": 17,
    "avg_duration_seconds": 0.697
  },
  {
    "tool": "run_test",
    "calls": 431,
    "error": 2,
    "avg_duration_seconds": 3.837
  },
  {
    "tool": "code_impact",
    "calls": 422,
    "error": 0,
    "avg_duration_seconds": 0.134
  },
  {
    "tool": "worktree_guard",
    "calls": 406,
    "error": 0,
    "avg_duration_seconds": 0.03
  },
  {
    "tool": "db_schema",
    "calls": 351,
    "error": 0,
    "avg_duration_seconds": 0.033
  }
]
```
