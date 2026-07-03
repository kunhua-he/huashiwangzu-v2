---
name: "false-success-audit-r8开工-假成功专项审计"
type: "task"
tags: [false-success-audit-r8, audit, false-success, dev-toolkit, 20260703]
agent: "false-success-audit-r8"
created: "2026-07-02T18:06:10.347566+00:00"
---

false-success-audit-r8 开工。范围：只做审计不改代码；优先 backend/app、modules、dev_toolkit 当前 dirty 相关链路；专项查 ApiResponse 外层 success true 包内部失败、except Exception pass、return skipped/completed 掩盖失败、测试 mock 掩盖。按要求先读 开发文档/README.md，并使用项目工具台 brief/plan_task/worktree_guard/code_explore。
