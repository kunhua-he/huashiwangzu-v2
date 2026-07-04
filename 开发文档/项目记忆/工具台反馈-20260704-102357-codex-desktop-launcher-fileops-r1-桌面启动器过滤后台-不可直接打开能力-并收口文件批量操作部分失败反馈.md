---
name: "工具台反馈-20260704-102357-codex-desktop-launcher-fileops-r1-桌面启动器过滤后台/不可直接打开能力，并收口文件批量操作部分失败反馈"
type: "reference"
tags: [mcp-feedback, dev-toolkit]
agent: "codex-desktop-launcher-fileops-r1"
created: "2026-07-04T10:23:57.648743+00:00"
---

# MCP 使用反馈

## 任务

桌面启动器过滤后台/不可直接打开能力，并收口文件批量操作部分失败反馈

## 顺畅度

- 评分：4/5
- 体感：整体顺畅，brief/plan_task/code_explore/worktree_guard/finish_task 能覆盖开工到收工。

## 本次用到的工具

brief, plan_task, worktree_guard, code_explore, code_node, code_impact, finish_task, memory_write, mcp_feedback

## 卡点 / 不顺手的地方

并行任务导致工作区 dirty 很多，finish_task 需要手动维护较长 baseline_paths；第二次 frontend build 被其他任务改动阻塞，工具只能记录不能自动归因到具体 agent。

## 缺少的工具 / 能力

缺少一个按本轮编辑历史自动生成 baseline/owned paths 的工具；也缺少前端 npm build/test 的结构化工具台 wrapper。

## 升级建议

finish_task 可支持从开工 worktree_guard JSON 自动识别新增 forbidden hits，并单独列出本 agent 触碰路径；增加 frontend_build/frontend_test 工具可减少 shell 输出噪声。

## 建议移除或合并的工具

无

## 其他备注

子代理并行有帮助，但多个子代理同时写项目记忆会让边界输出包含较多额外记忆文件。

## 当前工具热度快照

```json
[
  {
    "tool": "call_capability",
    "calls": 78,
    "error": 5,
    "avg_duration_seconds": 0.293
  },
  {
    "tool": "code_node",
    "calls": 75,
    "error": 0,
    "avg_duration_seconds": 0.142
  },
  {
    "tool": "code_explore",
    "calls": 51,
    "error": 0,
    "avg_duration_seconds": 0.353
  },
  {
    "tool": "worktree_guard",
    "calls": 37,
    "error": 0,
    "avg_duration_seconds": 0.029
  },
  {
    "tool": "run_test",
    "calls": 36,
    "error": 0,
    "avg_duration_seconds": 4.923
  },
  {
    "tool": "sql",
    "calls": 34,
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
    "calls": 26,
    "error": 0,
    "avg_duration_seconds": 0.58
  }
]
```
