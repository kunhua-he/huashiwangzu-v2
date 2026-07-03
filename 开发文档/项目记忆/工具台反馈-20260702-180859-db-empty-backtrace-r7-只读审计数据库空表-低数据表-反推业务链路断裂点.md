---
name: "工具台反馈-20260702-180859-db-empty-backtrace-r7-只读审计数据库空表/低数据表，反推业务链路断裂点"
type: "reference"
tags: [mcp-feedback, dev-toolkit]
agent: "db-empty-backtrace-r7"
created: "2026-07-02T18:08:59.788123+00:00"
---

# MCP 使用反馈

## 任务

只读审计数据库空表/低数据表，反推业务链路断裂点

## 顺畅度

- 评分：4/5
- 体感：整体顺畅：brief/db_schema/sql/code_node 能快速完成从表规模到写入点的反推。

## 本次用到的工具

brief, plan_task, worktree_guard, db_schema, code_explore, code_node, tail_log, sql, finish_task, memory_write, mcp_feedback

## 卡点 / 不顺手的地方

db_schema 只能列结构，不带 row count；需要手写 query_to_xml 动态 count。code_explore 对大范围自然语言查询会被 runtime/index.ts 的重复 tasks 命中稀释，需要再用 code_node/rg 精查。

## 缺少的工具 / 能力

建议增加 db_table_counts/empty_table_audit 工具：一次返回 exact_count、n_dead_tup、last_analyze、按前缀分组、疑似上下游反差。

## 升级建议

code_explore 可增加按路径前缀/表名写入点过滤，避免重复 runtime 模板文件占满展示预算。sql 结果可保留列名而不是 col0/col1，审计报告整理会更稳。

## 建议移除或合并的工具

无

## 其他备注

本次没有执行写入型 probe，符合只读审计要求。

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
    "calls": 274,
    "error": 0,
    "avg_duration_seconds": 0.016
  },
  {
    "tool": "sql",
    "calls": 234,
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
    "calls": 139,
    "error": 0,
    "avg_duration_seconds": 2.769
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
