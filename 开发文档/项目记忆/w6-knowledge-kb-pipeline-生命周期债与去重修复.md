---
name: "W6 Knowledge kb_pipeline 生命周期债与去重修复"
type: "task"
tags: [knowledge, kb_pipeline, lifecycle, dedupe, task-queue]
agent: "W6-codex"
created: "2026-07-02T11:40:18.010213+00:00"
---

# 改了什么
- 在 Knowledge 服务内新增 kb_pipeline 历史 File not found 债务 dry-run 分类：doc_deleted/doc_missing 归 obsolete，source_file_missing/source_file_deleted 建议 lifecycle_skip 并标明 would_set_parse_error，file_row_live 保留 retry_or_parser_investigation。
- kb_pipeline handler 对 deleted document 返回 skipped/obsolete；对源文件行缺失或已删除返回 skipped，并写 KbDocument.parse_error=source_file_missing/source_file_deleted，避免新增 failed。
- register_document 与 /documents/full-pipeline 统一走 enqueue_pipeline_task；该函数 dedupe pending/running，并加同 document advisory transaction lock，防手工重复入队。
- 新增/扩展 backend/tests/test_knowledge_pipeline_lifecycle.py 覆盖 source missing/deleted skipped、live file File not found 不误判、重复入队不重复。

# 验证
- ruff passed: modules/knowledge/backend/services/document_service.py, pipeline_service.py, pipeline_debt_service.py, backend/tests/test_knowledge_pipeline_lifecycle.py。
- pytest backend/tests/test_knowledge_pipeline_lifecycle.py: 5 passed。
- /api/health probe 200；backend tail_log 无新增输出。

# 风险/备注
- 工作区已有大量其他 agent/main session dirty，未 revert/checkout。
- finish_task 的 module boundary 报 outside_allowed，主要因为全局已有 dirty，且本任务按用户授权改了 backend/tests/test_knowledge_pipeline_lifecycle.py。
- 未重启后端；新增 dry-run route 需正常后端 reload 后生效。
- router.py 全文件 ruff 仍有历史 import/E712 噪声，本次未格式化整文件以避免扩大改动。
