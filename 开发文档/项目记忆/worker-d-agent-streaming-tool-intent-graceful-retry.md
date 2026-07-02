---
name: "Worker D Agent streaming tool intent graceful retry"
type: "task"
tags: [agent, streaming, tool-intent, retry]
agent: "parallel-repair-worker-d"
created: "2026-07-02T10:27:11.629201+00:00"
---

# 改了什么
- 将 single-pass streaming 中未完成 tool intent 从 error 结果改为 retry_tool_intent contract。
- ToolLoopRuntime 首次遇到该 contract 会追加内部重试指令并 continue；重复失败时降级为普通可恢复提示 token，不再发 error 事件。
- 补充 test_agent_tool_loop_runtime.py 覆盖 helper contract 和 run-level retry。

# 验证了什么
- lint: tool_loop_runtime.py passed；test_agent_tool_loop_runtime.py passed。
- run_test: backend/tests/test_agent_tool_loop_runtime.py backend/tests/test_assistant_draft.py ../modules/agent/backend/test_stream_emitter_guardrails.py -> 14 passed。

# 是否还有残留风险
- 未做真实 /api/agent/chat SSE 活栈探针。
- 工作树有并行 worker 的 unrelated dirty files，未回退。

# 关联 commit
- 未提交。
