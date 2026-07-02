---
name: "审计修复09验收通过并修正release gate阻断口径"
type: task
tags: ["audit", "release-gate", "task-queue", "sandbox", "mailbox"]
created: 2026-07-02
agent: codex
---

2026-07-02 Codex 验收 opencode 的“审计修复09-发布前回归矩阵与后台任务历史债治理”。发现并直接小修两点：1) task queue audit 原字段 new_failures_24h 实际是 1h 滚动窗口，改为 recent_failed_count + recent_failure_window_hours，避免语义误导；2) release_gate 不再用滚动 recent failed 判 BLOCKER，而是在 smoke 前记录 failed baseline，smoke 后用 failed delta 判定本次 gate 是否新增失败；同时 httpx 客户端加 trust_env=False，避免本地探针被代理环境污染报 Invalid port ':1'。最终验收：ruff 通过，test_task_queue_audit.py 7/7、test_framework_health.py 5/5、test_task_worker_recovery.py 4/4、dev_toolkit/test_release_gate.py 通过；module_sandbox_matrix 34 模块 pass=8 fail=0 skip=26；release_gate.py --skip-ui 输出 DEBT (PASS_WITH_DEBT)，failed 777->777 未新增，smoke 28/28 全绿。已将 09 蒸馏进 开发文档/变更历史.md，并删除 09 投件/回信目录。
