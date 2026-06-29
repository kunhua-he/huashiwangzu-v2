---
name: "Agent 端到端真实流式架构改造"
type: task
tags: ["agent", "streaming", "sse", "tool-calls", "gateway", "runtime", "frontend"]
created: 2026-06-28
agent: zcode
---

完成 Agent 单次端到端流式架构改造：Gateway 新增 StreamingToolCallAccumulator，将 OpenAI/DeepSeek streaming tool_calls 累积为 TOOL_CALL 事件；Runtime 新增 StreamProxy 和 assistant_stream_start/delta/rollback/commit 生命周期，ToolLoopRuntime 改为优先 streaming 决策路径并支持工具发现 rollback、final summary 逐 token 输出；Frontend 移除独立 streaming row，改为真实 MessageBubble provisional 流式渲染并支持 rollback/commit、来源与 usage 绑定延续。验证：gateway accumulator/protocol 测试 7 passed；changed Python files py_compile 通过；frontend npm run build 通过；/api/health 200。
