---
name: "knowledge-chain-probe-r7 知识库主链路审计与诊断收尾补修"
type: "task"
tags: [knowledge-chain-probe-r7, knowledge, pipeline, ingest, search, governance, db-audit]
agent: "knowledge-chain-probe-r7"
created: "2026-07-02T18:10:42.732699+00:00"
---

针对“知识库很多链路断”审计了 knowledge ingest->parse->chunks->search->governance 主链路。证据：能力注册包含 knowledge:ingest/search/get_ingest_status/get_pending_count/classify_pipeline_debt；路由 /api/knowledge/documents/parse、/search、/governance/*、/documents/{id}/ingest-status 可用；活接口 health/search/get_pending_count/pipeline-debt dry-run 均 200。DB 现状：kb_documents live 约 1159，kb_chunks 1126，kb_page_fusions 799，kb_governance_candidates 316，kb_pipeline_runs 57；framework_system_task_queues 中 kb_pipeline completed 770、failed 769。主要真实断点/债务：大量历史 failed 任务来自 doc_missing/source_file_missing/source_file_deleted，pipeline-debt dry-run 50 条样本中 doc_missing 23、source_file_missing 24、source_file_deleted 1、parser_no_content_blocks 2；另有 4 条历史 kb_pipeline_runs 仍 running，但对应框架队列任务已 completed/skipped，属于诊断账本历史残留。新近 source_file_deleted during fusion 路径已验证为 skipped 且 ingest-status 返回 source_unavailable。代码补修：modules/knowledge/backend/services/pipeline_orchestrator.py 在依赖失败提前退出分支补 _record_stage_run/_finish_pipeline_run/commit，避免该兜底路径留下 running 诊断；modules/knowledge/backend/tests/test_pipeline_stage_semantics.py 增强诊断 DB fake，并断言失败 stage 会把 pipeline run 标记 failed。验证：ruff 两文件通过；pipeline_stage_semantics 10 passed；knowledge sandbox 9 passed。未触碰 backend/app 既有脏文件；未批量修改真实 DB。
