---
name: "TaskQueue 与 KnowledgePipeline deleted-source 失败债务最终收口复验"
type: "task"
tags: [taskqueue, knowledge, release-gate, test-data-cleanup]
agent: "codex"
created: "2026-07-04T14:46:31.676447+00:00"
---

2026-07-04 复验并收口 TaskQueue/KnowledgePipeline failed 债务：核心代码提交 c2b7ac75 已实现 kb_deleted_source_obsolete 分类、audit/release_gate 语义与 knowledge pipeline debt 口径。主会话追加治理新出现的同类任务 5128（document_id=352, doc_deleted + no_file_row），最终 /api/tasks/worker/audit pending=0/running=0/failed=0，governance dry_run scanned=0。使用 test_data_pollution_cleanup 清理唯一测试污染 file 1557 / package 1385，最终 test_data_pollution active/content/uploads 均为 0。release_gate(preflight, skip_ui=true) 为 PASS_WITH_DEBT 且 blockers=[]，队列/Knowledge lifecycle/ContentPackage lifecycle/Test data pollution 均 PASS。相关 lint 全绿；测试 test_task_queue_audit 15 passed、test_knowledge_pipeline_lifecycle 11 passed、pipeline_debt_service 15 passed、test_release_gate 41 passed 1 skipped。剩余仅 preflight/skip-ui debt 与非本任务未跟踪 frontend/tests/ui-full-gate-contracts.spec.mjs。
