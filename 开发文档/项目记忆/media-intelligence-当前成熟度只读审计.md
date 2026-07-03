---
name: "media-intelligence 当前成熟度只读审计"
type: "task"
tags: [audit, media-intelligence, r6, read-only, maturity]
agent: "codex-audit-subagent-c"
created: "2026-07-03T16:17:06.037275+00:00"
---

2026-07-04 只读审计 modules/media-intelligence。结论：不是纯空架子，当前本地事实层已能在主栈读既有 PNG/MP4 文件，返回 Pillow metadata、average_intensity_hash、ffprobe metadata 和 ffprobe_timeline marker；sandbox pytest 6 passed，ruff passed，health/capability 可调用。也不是完整生产媒体智能：OCR、object detector、small-model、VLM 均明确 not_configured/degraded；keyframes 只是 timestamp marker，artifact_path 为 null；embedding 是 local_dedupe fingerprint，不是语义向量；前端是调试表单；runtime 是轻量子集；无 media_intelligence_* 持久化、无 knowledge/agent 消费闭环。主要风险是外层 HTTP success:true 容易被上层误读为算法完成，必须验收 stages[].status/degraded/artifacts 非空；另有 image-vision 图片本地事实层重叠，需收束避免双轨。返工原因：先交 provider/schema/manifest 骨架，后续才补坏参 422、本地 facts、degraded 语义和活栈样例，且 R6 多线程 dirty 混杂 knowledge/dev_toolkit/frontend tests，边界/验收信号被稀释。建议收敛：把模块定位为媒体分析编排契约；图片事实复用/对齐 image-vision，视频先接 media-asr，新增 adapter 前先定义 done/degraded 门禁和最小 gold set。无 commit。
