---
name: "reference_sources目录整理与知识库视频分析体系方案"
type: "task"
tags: [reference_sources, knowledge, video-analysis, rag, vlm, asr]
agent: "zcode"
created: "2026-07-02T18:13:48.820052+00:00"
---

Agent: zcode

本次完成：
1. 调项目工具台 brief/plan_task/worktree_guard/code_explore/capabilities/db_schema/tail_log，确认 knowledge 模块现状、边界与视频分析影响面。
2. 整理宿主机参考源码目录 `/Users/hekunhua/Documents/Agent/reference_sources`：保持顶层编号结构，补齐 `30_media_analysis_reference` 下 `00_pipeline_orchestration`、`05_video_decode_sampling`、`70_multimodal_models`、`80_storage_vector_index` 等分类，并将重复的 `2026_06_25_extra_duplicate_core_frameworks` 移到 `90_archive/`。
3. 通过本地 4780 代理新增下载 9 个参考项目：decord、PyAV、whisperX、FlagEmbedding、microsoft-graphrag、LLaVA-NeXT、Qwen2.5-VL、MiniCPM-V、lancedb。
4. 生成参考源清单：`/Users/hekunhua/Documents/Agent/reference_sources/00_catalog/video_analysis_reference_catalog.md`。
5. 多 agent 并行阅读视频解码/场景切分/OCR/ASR/VLM/检索/GraphRAG/向量存储参考源码，沉淀详细方案：`开发文档/03_模块开发文档/knowledge_video_analysis_system_plan.md`。
6. 在 `开发文档/03_模块开发文档/README.md` 与 `modules/knowledge/README.md` 增加视频分析方案入口。

核心结论：知识库视频分析第一版应先做“视频 asset → fixed 30s segment → FunASR 转写 → segment content_text → BGE-M3 向量化 → 搜索结果跳转视频时间点”的最小闭环；第二步加关键帧 OCR；第三步加 Qwen2.5-VL/Qwen-VL segment caption；之后再加视觉 embedding 与 GraphRAG。模型推荐 FunASR + Qwen 为主，MiniCPM-V 为 fallback，LLaVA-NeXT 只作研究基线；存储继续使用 PostgreSQL + pgvector + FTS + RRF + reranker。

验证：已验证 reference_sources 目录结构与新增 repo 清单；文档/调研任务未跑代码测试。

风险：工作区存在大量既有未提交变更，非本任务产生；reference_sources 在 git 仓库外，不受 snap_diff 覆盖；本次只改文档与仓库外参考源码目录，未改产品逻辑。

关联 commit：未提交。
