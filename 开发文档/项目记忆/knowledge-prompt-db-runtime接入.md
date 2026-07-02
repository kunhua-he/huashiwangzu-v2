---
name: "Knowledge Prompt DB runtime接入"
type: "task"
tags: [knowledge, prompt, db-template, 20260702]
agent: "codex-knowledge-prompt-db-worker"
created: "2026-07-02T14:39:22.221962+00:00"
---

本次作为 Knowledge Prompt DB 接入 worker，按限定范围把 Knowledge 运行路径中的硬编码 prompt 改为通过 modules/knowledge/backend/services/prompt_utils.py 的 load_prompt(db, template_name) 读取 framework_prompt_templates。改动点：fusion_service/profile_service/entity_service/raw_collection_service 改为运行时读取模板；prompt_utils 增加 raw OCR/vision 模板名和 db=None 短 fallback；modules/knowledge/backend/init_db.py 幂等 seed knowledge_profile_system、knowledge_entity_extraction、knowledge_page_fusion、knowledge_page_fusion_legacy、knowledge_raw_ocr、knowledge_raw_vision；新增 backend/tests/test_knowledge_prompt_runtime.py，用 fake load_prompt/gateway 验证 fusion/entity/profile 实际入口把 DB 模板传给 gateway。验证：ruff 覆盖改动 Python 文件全通过；pytest backend/tests/test_knowledge_prompt_runtime.py + backend/tests/test_prompt_read.py 共 13 passed；/api/knowledge/health 返回 ok。注意：工作区已有并行改动（pipeline_service/pipeline_debt_service、agent/dev_toolkit 等），本任务未回退也未修改那些文件；finish_task 边界因 backend/tests 和既有脏文件报告 false。关联 commit：未提交。
