---
name: "Knowledge 链路升级审计 explorer 结论"
type: "task"
tags: [knowledge, audit, pipeline, prompt, ir, source-file, 20260702]
agent: "codex-knowledge-audit-explorer"
created: "2026-07-02T14:23:03.745270+00:00"
---

只读审计 Knowledge 文件上传/注册/解析/分块/融合/检索/证据详情链路。结论：主链路已由 file.uploaded -> knowledge:ingest -> register_document -> kb_pipeline 串起，并有 ingest_status/source_unavailable/search live-source 过滤；但仍存在 HTTP 手动阶段入口与 capability/事件入口并存，/documents/chunk 会从已有 chunks 反推 DocumentIr 并删除重建，属于第二入口风险。Prompt DB 表与只读 by-name 入口存在，DB 里有 4 条 knowledge_* 模板，但当前 fusion/profile/entity/raw 服务仍使用硬编码 prompt 常量，prompt_utils.load_prompt 未被消费，seed.py 也未 seed knowledge 模板。Content IR 与 Knowledge DocumentIr 并存：register_document 会尝试 content:pipeline 并保存 content_package_id，parse_and_index 优先读取 ContentPackageVersion.content_json，否则 fallback parser capability；随后扁平化为 legacy blocks，resource/children/metadata 均有丢失风险。治理方面，source_file_deleted/missing 已有状态和 dry-run 工具，但历史 failed 队列仍多，dry-run 不落地；Parser returned no content blocks 仅有失败态和少量统计，缺少分类/重试/样本诊断工具。活数据：framework_system_task_queues knowledge failed File not found 约 710，Parser no content 14；kb_documents parse_error File not found 168，Parser no content 2，source_file_deleted 32，source_file_missing 1；live docs missing file row 600，deleted file 351。未改代码。
