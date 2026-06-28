---
name: "Agent 单轮 token 用量跨调用累加"
type: task
tags: ["agent", "token-usage", "accumulation", "SSE", "frontend"]
created: 2026-06-28
agent: zcode
---

新增整轮 token 用量统计：在 tool_loop_runtime 中初始化 _accumulated_usage dict，在每次非流式(chat_with_degradation_chain)和流式(emitter.yield_final_stream)调用后提取 API 返回的 prompt_tokens/completion_tokens/total_tokens 并累加；最终落库时优先写入 _accumulated_usage，同时通过 round_usage SSE 事件推送到前端；前端接收 round_usage 后写入消息 usage 字段，MessageBubble 组件自动显示。
