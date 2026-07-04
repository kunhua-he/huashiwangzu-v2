---
name: "TaskQueue 与 KnowledgePipeline deleted-source 失败债务治理收口"
type: "task"
tags: [task-queue, knowledge, release-gate, debt-governance]
agent: "codex"
created: "2026-07-04T14:31:54.513331+00:00"
---

2026-07-04 执行审计修复：将 kb_pipeline 中 document 已删除且 file row 不存在的 failed 任务分类为 kb_deleted_source_obsolete / mark_obsolete，audit 区分 active recent failure 与 deleted-source obsolete debt，release_gate 单独展示该队列项；knowledge pipeline debt 能力补 Invalid or unsupported image content marker 与 doc_deleted archive_obsolete 口径。活系统治理 task 2930/2946：dry_run 2 个 mark_obsolete，非 dry_run processed=2，任务行保留并写 result.status=obsolete、previous_error、previous_parameters；治理后 /api/tasks/worker/audit 显示 pending=0/running=0/failed=0。验证：ruff 相关文件通过；backend/tests/test_task_queue_audit.py 15 passed；backend/tests/test_knowledge_pipeline_lifecycle.py 11 passed；modules/knowledge/backend/tests/test_pipeline_debt_service.py 15 passed；dev_toolkit/test_release_gate.py 39 passed/1 skipped；release_gate preflight skip_ui 无 queue blocker。全量 backend pytest 仍有 10 个非本任务失败，集中在 memory/office/terminal/web 既有或并行改动。提交：c2b7ac75。
