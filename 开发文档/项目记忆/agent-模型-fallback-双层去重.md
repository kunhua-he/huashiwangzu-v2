---
name: "Agent 模型 fallback 双层去重"
type: "task"
tags: [agent, fallback, gateway, 20260702]
agent: "codex-agent-fallback-dedupe-worker"
created: "2026-07-02T14:38:00.471806+00:00"
---

# 改了什么
- 将 Agent engine fallback wrapper 收窄为兼容壳：`chat_with_degradation_chain` / `chat_stream_with_degradation_chain` 保留函数名，但只经 `fallback_chain.py` 委托 `gateway_router.chat` / `gateway_router.chat_stream` 一次。
- 删除 Agent 外层按 `FALLBACK_CHAIN` 的非流式和流式重复循环；gateway 成为唯一 fallback 裁判。
- 流式 wrapper 透传 gateway 的 `degradation` / `token` / `error` / `done` 等事件，不再把 gateway error 当异常触发 Agent 侧二次降级，也不额外追加 Agent 层 `done`。
- 补 `modules/agent/backend/engine/test_fallback_chain.py` 单测，证明非流式与流式 wrapper 都只调用 gateway 一次，且流式事件原样透传。

# 验证了什么
- `backend/.venv/bin/ruff check modules/agent/backend/engine/fallback_chain.py modules/agent/backend/engine/engine.py modules/agent/backend/engine/test_fallback_chain.py` 通过。
- `pytest ../modules/agent/backend/engine/test_fallback_chain.py backend/tests/test_gateway_retry.py backend/tests/test_agent_tool_loop_runtime.py backend/tests/test_engine_batch2.py::TestEngineIntegration` 合跑 21 passed。

# 残留风险
- 当前 worktree 有其他 agent 的 backend/tests、dev_toolkit、knowledge、agent task/profile dirty 文件；本任务未修改也未回退。

# 关联 commit
- 未提交。
