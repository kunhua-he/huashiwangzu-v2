---
name: "工具台反馈-20260704-102143-codex-desktop-launcher-open-feedback-r1-收口桌面启动器过滤、命令搜索后台能力标注、openWindow null"
type: "reference"
tags: [mcp-feedback, dev-toolkit]
agent: "codex-desktop-launcher-open-feedback-r1"
created: "2026-07-04T10:21:43.255040+00:00"
---

# MCP 使用反馈

## 任务

收口桌面启动器过滤、命令搜索后台能力标注、openWindow null 用户可见反馈

## 顺畅度

- 评分：4/5
- 体感：工具台整体顺畅，CodeGraph 和 finish_task 对定位与收口有帮助。

## 本次用到的工具

brief, plan_task, worktree_guard, code_explore, code_node, code_impact, finish_task, memory_write, mcp_feedback

## 卡点 / 不顺手的地方

当前多 worker 并行导致同文件和允许边界外不断出现新改动，finish_task 的边界报告会把并行新增混入本轮，需要人工解释。

## 缺少的工具 / 能力

缺少能声明“这些路径属于其他 agent 并行新增”的实时协作归因工具。

## 升级建议

worktree_guard/finish_task 可支持按时间或 diff owner 标记并行新增，或者允许传入“本轮 touched file manifest”作为主判定。

## 建议移除或合并的工具

无

## 其他备注

本轮未创建用户侧新线程；动态工具里没有隐藏子代理/子任务工具，只有 create_thread。

## 当前工具热度快照

```json
[
  {
    "tool": "code_node",
    "calls": 75,
    "error": 0,
    "avg_duration_seconds": 0.142
  },
  {
    "tool": "call_capability",
    "calls": 54,
    "error": 5,
    "avg_duration_seconds": 0.305
  },
  {
    "tool": "code_explore",
    "calls": 51,
    "error": 0,
    "avg_duration_seconds": 0.353
  },
  {
    "tool": "worktree_guard",
    "calls": 36,
    "error": 0,
    "avg_duration_seconds": 0.029
  },
  {
    "tool": "run_test",
    "calls": 35,
    "error": 0,
    "avg_duration_seconds": 4.822
  },
  {
    "tool": "sql",
    "calls": 33,
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
    "calls": 23,
    "error": 0,
    "avg_duration_seconds": 0.623
  }
]
```
