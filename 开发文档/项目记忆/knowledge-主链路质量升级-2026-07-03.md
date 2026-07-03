---
name: "knowledge 主链路质量升级 2026-07-03"
type: "task"
tags: [knowledge, quality, ingest, progress, llm-diagnostics]
agent: "codex-knowledge-module-worker-20260703-r1"
created: "2026-07-03T06:08:38.725380+00:00"
---

Agent codex-knowledge-module-worker-20260703-r1 完成 modules/knowledge 主链路质量升级：ingest status 的 graph 阶段不再因 kb_chunk_entities 为空而假失败/假未开始，补充 node_count/chunk_entity_count；progress service 暴露 source_unavailable/source_file_deleted；dashboard 排除源文件缺失文档的 completed/recent 并计入 failed/source_unavailable；LLM diagnostics stream 去除空 fallback 假成功，fusion/profile/entity 服务接入 timed_llm_chat 慢调用诊断；前端 API 类型与进度、仪表盘展示同步更新；README 增加主链路质量契约。验证：targeted pytest 20 passed，knowledge sandbox 通过，frontend build 通过，live health/search/get_ingest_status probe 可用，直接 DB/service 检查 source_unavailable 与 dashboard 计数正确。未提交 commit。注意：agent_board_heartbeat 返回 task not found；全量 knowledge lint/pytest 仍有既有未触碰问题。
