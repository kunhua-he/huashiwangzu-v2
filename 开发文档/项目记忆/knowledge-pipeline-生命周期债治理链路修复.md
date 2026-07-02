---
name: "knowledge pipeline 生命周期债治理链路修复"
type: "task"
tags: [knowledge, pipeline-debt, lifecycle, task-queue, 20260702]
agent: "codex-knowledge-lifecycle-worker"
created: "2026-07-02T15:22:35.349238+00:00"
---

# 我是谁
codex-knowledge-lifecycle-worker

# 干了什么
- 补齐 knowledge pipeline 历史债治理链路：`classify_pipeline_lifecycle_debt` 现在覆盖 `File not found`、`Document % not found`、`Parser returned no content blocks`，输出 `archiveable`/`retryable` 安全标志。
- 新增受控 `apply_pipeline_lifecycle_debt_action`：`archive_obsolete` 只把 doc/source lifecycle 类失败归档为 completed + result.status=skipped；`retry_live` 只重排 `file_row_live`，不会重试 `doc_deleted`，不会自动处理 parser quality debt。
- `pipeline_service` 既有 handler 已能对 doc_missing/doc_deleted/source unavailable 返回 skipped；本次延续并用测试覆盖治理侧闭环。
- 新增 `/api/knowledge/governance/pipeline-debt/apply`（默认 dry_run=true）和 admin 只读能力 `knowledge:classify_pipeline_debt`；同步 manifest public_actions 元数据。

# 改动文件
- modules/knowledge/backend/services/pipeline_debt_service.py
- modules/knowledge/backend/router.py
- modules/knowledge/manifest.json
- backend/tests/test_knowledge_pipeline_lifecycle.py

# 验证
- ruff: `modules/knowledge/backend/services/pipeline_debt_service.py` passed
- ruff: `modules/knowledge/backend/router.py` passed
- pytest: `backend/tests/test_knowledge_pipeline_lifecycle.py` 10 passed
- `/api/health` 200，worker running
- 代码导入检查确认 pipeline-debt 路由有 GET dry-run 与 POST apply
- 活栈旧 dry-run 样本前 500 条：source_file_missing=318，source_file_deleted=169，file_row_live=13

# 剩余真实债
- 未直接清 DB，历史 failed 仍存在；健康接口显示 task_queue failed=899。
- 由于未重启后端，活栈 OpenAPI 仍是旧路由视图，新 POST apply 要等后端重启加载。
- 工作区已有大量其他 agent dirty，未做 commit；关联 commit：无。
