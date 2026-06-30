---
name: "Agent底座维修11 — 异步上下文压缩移出首包关键路径"
type: task
tags: ["agent", "compaction", "async", "latency", "critical-path", "LLM"]
created: 2026-06-30
agent: opencode
---

将语义压缩从请求关键路径改为异步后台任务。修前 request_id=fe7684b7 首包 26.8s（压缩 18.8s + 思考路由 6.8s）。修法：新建 `agent_context_compactions` 表持久化压缩状态，`run_post_turn_hooks` 自动入队 `agent_context_compact`，worker 内调 `compress_middle` 后原子写 `ready`；请求路径 `_load_compacted_context` 只读 `ready` 记录或回退原始事件，超预算仅确定性裁尾（无模型调用）。思考路由移除 LLM fallback 直达 `medium`。编辑触发 compaction 失效。新增 `project_messages_with_compaction` 自定义投影。15 个单元测试覆盖状态/幂等/水位/工具完整性。commit: 23a33bf
