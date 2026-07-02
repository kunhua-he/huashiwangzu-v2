---
name: "Agent 主链路审计 explorer：gateway/fallback/任务队列/capability 交互结论"
type: "task"
tags: [agent, audit, gateway, fallback, task-queue, capability, 20260702]
agent: "codex-agent-mainlink-audit-explorer"
created: "2026-07-02T14:23:11.740484+00:00"
---

只探查不改代码。结论：主 /api/agent/chat 入口进入 ConversationRuntime -> ToolLoopRuntime，工具执行经 skill_* 或 call_capability，knowledge/memory/tools 未发现直接 import 其他模块或直读对方业务表。云模型失败当前有 gateway 内置 fallback 覆盖，健康探针显示 opencode/llama/local true，ollama/mimo false。发现三类风险：1) Agent engine/fallback_chain.py 与 backend/app/gateway/router.py 都各自编排 models.json fallback_chain，同一调用存在双层 fallback，可能造成重复调用和降级事件口径混乱；2) RuntimeTaskSink.persist_pending_events 以成功数量推进 persisted_event_count，中间失败后会跳过失败事件并可能重复后续事件，存在丢事件/双写风险；3) memory_distill、memory_dream 后台 handler 内部吞掉 memory/LLM 失败但返回 status ok，任务队列会 completed，属异步假绿。另：README 说工具决策非流式，但默认 RuntimePolicy.enable_single_pass_streaming_tools=True，实际工具决策走流式工具检测。
