---
name: "Sandbox 矩阵纯前端模块 README 验收命令补齐"
type: "task"
tags: [sandbox, matrix, modules, verification]
agent: "codex-sandbox-matrix-worker-20260703-r1"
created: "2026-07-03T06:03:56.208021+00:00"
---

# 改了什么
为 6 个纯前端模块补齐 README 中可复现 sandbox 验收命令：doc-viewer、hello-world、image-viewer、pdf-viewer、ppt-viewer、text-editor。命令覆盖模块 sandbox npm install/build、主框架 frontend build、module_sandbox_matrix --check。未修改 agent、knowledge、backend/app、frontend/src、dev_toolkit。

# 验证了什么
- module_sandbox_matrix(check=true) returncode=0，所有可运行 sandbox/backend 测试和 sandbox frontend build 通过。
- cd frontend && npm run build 通过。
- git diff --check 针对本次 6 个 README 通过。
- 开工 worktree_guard 为 0 changed；收工时工作区出现并行任务的 backend/app、dev_toolkit、modules/agent、modules/knowledge 等无关脏文件，未由本任务修改。

# 残留风险
无代码行为改动；本次是文档验收命令补齐。agent_board_heartbeat 因 task not found 无法落盘，已在 MCP 反馈记录。

# 关联 commit
未提交。
