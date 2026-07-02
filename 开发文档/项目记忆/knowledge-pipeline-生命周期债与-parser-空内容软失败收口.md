---
name: "knowledge pipeline 生命周期债与 parser 空内容软失败收口"
type: "task"
tags: [knowledge, pipeline, debt, parser, 20260702]
agent: "knowledge-chain-worker"
created: "2026-07-02T16:04:00.535450+00:00"
---

# 做了什么

- 审计 knowledge 文件/文档/任务队列/解析/分块/检索/治理 debt 链路，重点看 File not found、doc_deleted obsolete、file_row_live、Parser no content。
- 修复 pipeline debt apply：归档 source_file_missing/source_file_deleted 历史失败任务时，同步调用 mark_document_source_unavailable，把对应知识文档活动/错误状态暂停并写入 source_file_missing/source_file_deleted 诊断，避免队列归档后文档仍停在解析失败态。
- 修复 parser 空内容链路：parse_document 标出的 empty_result 不再让 parse_and_index_document 抛硬失败截断 kb_pipeline，而是把文档 parse_status 标为 degraded、记录 Parser returned no content blocks: empty_result，并允许后续 raw/OCR/fusion 继续跑。
- 调整 search_ready/ingest status：parser 空内容 degraded 但后续融合索引已产出 chunks 时，仍可标记 search_ready，同时 pipeline_status 保持 degraded 以保留诊断。
- 加固 lifecycle 测试动态导入，优先复用 modules.knowledge.backend 路径，降低混跑时双包名前缀导致 SQLAlchemy 重复注册的风险。

# 验证

- ruff: document_service.py、pipeline_service.py、pipeline_debt_service.py、ingest_status_service.py、backend/tests/test_knowledge_pipeline_lifecycle.py、modules/knowledge/backend/tests/test_ingest_status_service.py 全部 All checks passed。
- pytest: backend/tests/test_knowledge_pipeline_lifecycle.py 11 passed。
- pytest: modules/knowledge/backend/tests/test_ingest_status_service.py 8 passed。
- pytest: cd backend && env JWT_SECRET=test-secret-for-knowledge-focused .venv/bin/pytest tests/test_knowledge_*.py => 15 passed。
- probe: /api/health 200 ok；/api/knowledge/governance/pipeline-debt/dry-run?limit=10 200，当前常驻后端仍为旧运行代码字段，未重启以免把共享脏工作区中其他 agent 的 backend/app 改动一起载入。

# 风险/备注

- 当前工作区有大量非本任务 dirty 文件，worktree_guard/finish_task 因既有 backend/app、dev_toolkit、其他模块等改动失败；本轮实际触碰范围为 modules/knowledge/** 和 backend/tests/test_knowledge_pipeline_lifecycle.py。
- modules/knowledge/backend/tests 整目录混跑仍会遇到既有双包名前缀重复导入 SQLAlchemy 表的收集问题；改动相关模块测试单跑通过。
- 未提交 commit。
