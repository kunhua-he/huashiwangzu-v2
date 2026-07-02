---
name: "工具台反馈-20260702-152322-codex-viewer-sandbox-worker-补齐 doc-viewer、image-viewer、pdf-viewe"
type: "reference"
tags: [mcp-feedback, dev-toolkit]
agent: "codex-viewer-sandbox-worker"
created: "2026-07-02T15:23:22.477712+00:00"
---

# MCP 使用反馈

## 任务

补齐 doc-viewer、image-viewer、pdf-viewer、ppt-viewer、text-editor 五个纯前端模块 sandbox，并通过真实 Vite build 与 sandbox matrix 验收。

## 顺畅度

- 评分：4/5
- 体感：整体顺畅，brief/plan_task/worktree_guard/codegraph/matrix 收口都能支撑这类 sandbox 补齐任务。

## 本次用到的工具

brief, plan_task, worktree_guard, code_explore, code_node, code_impact, finish_task, memory_write, mcp_feedback

## 卡点 / 不顺手的地方

worktree_guard 在已有大量其他 agent 脏改时会整体 success=false，需要人工区分开工前脏改与本次新增边界；另外 code_impact 对尚不存在的新文件只能返回 symbol not found。

## 缺少的工具 / 能力

希望有一个按 allowed_prefixes 只输出本次 untracked/tracked 可提交文件的轻量 summary，自动忽略 ignored dist/node_modules。

## 升级建议

finish_task 如果传入 allowed_prefixes，可在结果里单独列出 allowed 新增文件与 outside pre-existing dirty，便于多人同分支并行维修。

## 建议移除或合并的工具

无

## 其他备注

本次没有使用后端 probe/run_test，因为任务验收定义为纯前端 Vite build 与 sandbox matrix。

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
    "calls": 72,
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
