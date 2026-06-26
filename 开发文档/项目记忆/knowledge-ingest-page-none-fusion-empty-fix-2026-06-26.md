---
name: "knowledge-ingest-page-none-fusion-empty-fix-2026-06-26"
type: task
tags: ["knowledge", "ingest", "pipeline", "fix"]
created: 2026-06-26
agent: codex
---

修复 knowledge 入库后台管线的 txt/md 空内容问题：text-parser 返回 page=None 的块，raw_collection 原来按 page==1 精确过滤导致 raw content 为空，fusion 继续落空正文，kb_chunks 为 0。现将 page=None 归入第 1 页，并让 fusion 在单轮有效文本或 LLM 空 fused_text 时回退到原始文本。验证：knowledge embedding pipeline pytest 7 passed；真实上传 codex_live_kb_clean_* 走 file.uploaded→ingest→kb_pipeline，kb_raw_data/kb_page_fusions/kb_chunks/embedding 均有行，任务 completed 后清理测试数据。
