---
name: "R6-B knowledge parser greenlet 与 stale parse lock 修复"
type: "task"
tags: [r6, knowledge, parser, greenlet, stale-lock, retry]
agent: "codex-r6-knowledge-defects-b"
created: "2026-07-03T16:05:17.122506+00:00"
---

# 改了什么
- 修复 `modules/knowledge/backend/services/document_service.py`：`parse_and_index_document` 在声明 parsing 前快照 `file_id`、`extension`、`content_package_id`，后续 parser 调用使用普通变量，隔离提交后 ORM 属性访问/lazy-load 触点。
- 增加 stale parse lock 释放：当文档处于 `parsing`，`parse_started_at` 超过 30 分钟或缺失，且没有 pending/running `kb_pipeline` 队列任务时，释放旧锁并重新进入真实解析；有活跃任务或未超时仍返回 409，不吞错。
- 页级融合 helper 内部 commit 后显式 `refresh(doc)` 再更新向量状态，减少后续状态写入的陈旧对象风险。
- 新增 `modules/knowledge/backend/tests/test_pipeline_stage_semantics.py` 单测：覆盖提交后不再访问 `doc.file_id/doc.extension` 的快照路径，以及无活跃任务 stale `parsing` 锁可重新解析。

# 验证
- Ruff: `document_service.py`、`test_pipeline_stage_semantics.py` 通过；相关 debt/ingest/reconcile 测试文件也通过。
- Pytest: `test_pipeline_stage_semantics.py` 14 passed；`test_pipeline_debt_service.py` + `test_ingest_status_service.py` + `test_pipeline_reconcile_service.py` 26 passed；finish_task 合跑 43 passed。
- 活系统: `/api/knowledge/health` 200；`/api/health` 200；`knowledge:classify_pipeline_debt` 200。
- 活系统债务快照：summary 包含 `async_context_error=4`、`parser_no_content_blocks=2`、`file_row_live=13`、`duplicate_or_stale_parse_lock=1`；全量 SQL 原始失败标记为 `greenlet=4`、`Document already parsing=6`、`parser_empty=16`。

# 剩余风险
- 框架 `AsyncSessionLocal` 已设置 `expire_on_commit=False`，所以 greenlet 根因不只是普通 commit 过期；本次修复先消掉 parse 入口最危险的 ORM 属性访问触点并加测试防回归。
- 未自动重排 `parser_no_content_blocks`，它仍是 parser 质量/空内容问题，不适合无脑 retry。
- 本轮收工时 worktree 出现并发 dirty：`dev_toolkit/`、`frontend/tests/`、`modules/media-intelligence/` 以及若干非本轮 knowledge 文件；我未回滚。我的手动 diff 仅覆盖 `document_service.py` 与 `test_pipeline_stage_semantics.py`。

# 关联 commit
- 未提交。
