---
name: "紧急维修08历史Knowledge重复数据收口"
type: task
tags: ["knowledge", "数据库治理", "唯一索引", "冲突清理", "紧急维修08"]
created: 2026-06-29
agent: codex
---

按用户授权继续收口数据库冲突：查询确认唯一阻塞为 kb_documents owner_id=4,file_id=218 的未删除重复文档 {199,200}；关联 framework_file_items.id=218 已 deleted=true，两个文档均 pending/pending、total_chunks=0，kb_chunks 无关联记录，判定为非种子历史污染/冲突数据。通过 DELETE /api/knowledge/documents/199 和 /api/knowledge/documents/200 软删。重启后端触发 knowledge init_db 幂等索引创建，验证 pg_indexes 中 ux_kb_documents_owner_file_active 已存在，定义为 UNIQUE(owner_id,file_id) WHERE NOT deleted；重复冲突查询为空；/api/health status=ok；id>3000 语义失败 completed 查询为空。额外清理本轮运行产生的 untracked backend/data/agent/stuck_rounds.json.lock。commit: 未提交。
