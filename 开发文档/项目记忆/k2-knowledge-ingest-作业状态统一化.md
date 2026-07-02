---
name: "K2 knowledge ingest 作业状态统一化"
type: "task"
tags: [knowledge, ingest, task-queue, visibility, k2]
agent: "codex-k2"
created: "2026-07-02T12:33:41.845662+00:00"
---

# 改了什么
- 在 `modules/knowledge/backend/services/document_service.py` 中让 `register_document` 对新文档、已有未完成文档、已有进行中文档返回稳定任务元数据：`task_id/enqueued/reason/stage/status/pipeline_status/search_ready/deep_ready/stage_summary`。
- 新增 `modules/knowledge/backend/services/ingest_status_service.py`，按 `framework_system_task_queues.parameters.document_id` 解析 `kb_pipeline` 任务，聚合 `kb_documents` parse/vector/raw/fusion 状态、profile/graph/relation 计数、task 状态、last_error、next_action。
- 在 `modules/knowledge/backend/router.py` 增加 HTTP `GET /api/knowledge/documents/{document_id}/ingest-status` 与 capability `knowledge:get_ingest_status`；`knowledge:ingest` 返回统一状态字段，避免把“已入队”误说成“可检索/深度完成”。
- 更新 `modules/knowledge/manifest.json`、`modules/knowledge/README.md`、`modules/knowledge/sandbox/test_module.py`，新增 `modules/knowledge/backend/tests/test_ingest_status_service.py`。

# 验证了什么
- `ruff check` 通过：`document_service.py`、`ingest_status_service.py`、`test_ingest_status_service.py`。
- `python -m py_compile` 通过：router/document_service/ingest_status_service/test。
- `pytest modules/knowledge/backend/tests/test_ingest_status_service.py`：5 passed。
- `python3.14 modules/knowledge/sandbox/test_module.py`：PASS。
- `/api/health`：200 ok。

# 残留风险
- 并行 worker 在本轮期间产生 `backend/app/gateway/router.py`、`backend/data/config/models.json`、`backend/tests/test_gateway_retry.py` 等越界 dirty；未回退。
- `modules/knowledge` 内同时存在 K1/main 的其他改动（source filtering / pipeline stage semantics 等），K2 已按当前文件集成并通过 targeted 验证。
- 未跑 router.py 全文件 ruff 作为通过项，因为该文件已有 import/E712 债且本轮有并行同文件改动。

# 关联 commit
- 未提交。
