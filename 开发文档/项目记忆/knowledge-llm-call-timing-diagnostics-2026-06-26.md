---
name: "knowledge-llm-call-timing-diagnostics-2026-06-26"
type: reference
tags: ["knowledge", "llm", "diagnostics", "profile", "graph", "opencode"]
created: 2026-06-26
agent: Codex
---

本次给 knowledge 模块的 LLM 调用加了结构化耗时日志：新增 services/llm_diagnostics.py，并接入 profile_service、entity_service、fusion_service、search_service；document_service 的旧页融合路径也补上传 document_id/page。

日志格式：LLM_CALL_START / LLM_CALL_END / LLM_CALL_ERROR，包含 stage、profile_key、document_id、page、input_chars、user_chars、elapsed_ms、output_chars、tokens、ok，以及页数/正文长度等 extra 字段。retry_count 目前在模块层不可见，日志标记为 unavailable_at_module_layer；真实 retry 次数需要后续单独改框架 gateway 才能暴露。

实测 clean marker CODEX_LLM_DIAG_CLEAN_347d5b23b3：一个 93 字正文 txt，画像 document_profile 输入 609 chars，deepseek-v4-flash/opencode 耗时 9500.5ms；图谱 graph_entity_extract 输入 528 chars，耗时 32845.7ms。请求命中 https://opencode.ai/zen/go/v1/chat/completions 且 HTTP 200 返回内容，说明此次慢点不是 vision/qwen3-vl key 过期，而是普通文本 LLM 上游通道慢/排队/限速。

验证：py_compile 通过；knowledge 相关聚焦测试 test_raw_text_round_keeps_page_none_blocks 和 test_fusion_falls_back_when_llm_returns_empty_text 通过。完整 test_embedding_pipeline 中 1 个旧 e2e 用例失败，原因是上传自动后台管线与测试内同步 parse 并发，导致 embedding 行数 2 vs parse 返回 1；非本次日志改动直接引起。测试/验证产生的 doc_id 202/203、file_id 1830/1831、任务队列及相关文档产物已清理。
