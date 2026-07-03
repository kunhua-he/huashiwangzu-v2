---
name: "memory 模块深度质量升级：参数校验、向量维度、chunk 清理与经验反馈修复"
type: "task"
tags: [memory, audit, quality, embedding, chunk, experience]
agent: "codex-memory-module-worker-20260703-r1"
created: "2026-07-03T06:25:03.394206+00:00"
---

# 改了什么
- 仅修改 modules/memory/**：补齐 save/recall/list/delete/fuse/rethink/replace/insert/dream/experience/stable_rules/chunk/backfill 链路质量守卫。
- 增加统一 limit/offset/id/text 校验，坏参数从 500 收口为结构化 422。
- embedding 写入前校验 1024 维有限数值，所有 pgvector cast 明确 vector(1024)。
- 删除/ dream 合并记忆时同步清理 memory_chunks 和 memory_links；run_init 会清理历史 orphan chunks/links，并给 memory_chunks.embedding 建 vector index。
- 修复 experience_feedback(success=false) 的 asyncpg AmbiguousParameterError，改用 has_note 布尔参数避免 :note_payload 类型歧义。
- manifest/README 对齐 19 个 memory 能力，sandbox 增加质量守卫断言。

# 验证了什么
- ruff：memory 改动 Python 文件全部通过。
- sandbox：modules/memory/sandbox/test_module.py 25 passed。
- 活系统：后端重启后 /api/health ok；bad limit probes(list/recall/recall_chunk/match_experience) 返回 422；save/replace/insert/rethink/delete/fuse/recall 通过；save_experience/match_experience/experience_feedback 通过。
- 测试数据：memory record id 82 删除后 records/chunks/links 均 0；experience id 2 通过唯一 trigger 删除，remaining=0。
- DB 复核：orphan_chunks=0，orphan_links=0；record/chunk embeddings 均为 1024 维。

# 残留风险
- backfill_embeddings dry-run 仍显示 memory_records 43 total / 20 with_embedding / 23 missing；backfill_links dry-run 有 5 candidates，留作 admin-governed 数据治理。
- 仓库存在多个其他 worker 的 dirty 文件，finish_task 边界检查因此整体标红；本次实际 git diff -- modules/memory 只包含 memory 模块文件。

# 关联 commit
未提交。
