---
name: "TaskQueue KnowledgePipeline 5138 追加治理与最终门禁复核"
type: "task"
tags: [taskqueue, knowledge, release-gate, final-validation]
agent: "codex"
created: "2026-07-04T14:54:11.007853+00:00"
---

2026-07-04 最终复核执行信时，发现新同类 kb_pipeline failed task 5138（document_id=362, doc_deleted + no_file_row, retry_count=3, error=Invalid or unsupported image content）。先 dry_run 分类为 kb_deleted_source_obsolete/action=mark_obsolete，再非 dry-run 单条治理，未删除队列表行，result 保留 previous_error 与 previous_parameters。等待后台 pipeline 完成后，最终 /api/tasks/worker/audit 为 pending=0/running=0/completed=370/failed=0，governance dry_run scanned=0；test_data_pollution_audit active/recycled/knowledge/content/uploads 全 0；release_gate(preflight, skip_ui=true) 为 PASS_WITH_DEBT 且 blockers=[]，队列全部 PASS，git worktree clean sha=35a7fe73。
