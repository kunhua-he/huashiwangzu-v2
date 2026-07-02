---
name: "Memory/Profile 链路审计：profile_evolve 与 memory capability"
type: "task"
tags: [memory, agent, profile_evolve, task_queue, audit, 20260702]
agent: "codex-memory-profile-audit-explorer"
created: "2026-07-02T14:22:37.061201+00:00"
---

只探查不改代码。结论：当前 Agent 代码中未发现旧裸 `from init_db import ...` 残留，历史 `profile_evolve` 的 `No module named 'init_db'` 为旧代码债；现有 `profile_evolve` 对 LLM 空响应/JSON 解析失败返回 `{"error": ...}`，会被 `task_worker._result_is_semantic_failure` 视为语义失败并重试到 failed，不满足 soft failure 要求；memory save/recall/experience/dream/stable-rule 主链路通过 `memory:*` capability 暴露，Agent 侧 `layered_memory.py`/`experience_memory.py` 经 `call_capability` 调用，未见 Agent 直读 memory 表；但 memory 模块内 HTTP endpoint 与 capability endpoint 有薄逻辑重复。活系统证据：`/api/health` worker 注册 profile_evolve/memory_distill/memory_post_save，memory overview_stats 与 agent get_my_profile capability 200。SQL：profile_evolve failed 共 135，其中 `No module named 'init_db'` 130（2026-06-23 至 2026-06-29），`Failed to parse profile JSON` 3；历史 init_db failed 130 行对应 68 个 conv/owner，当前 active_conversation=0，可归档；若重跑，只应按 `(conversation_id, owner_id)` 去重且跳过 deleted/missing conversation。未改代码，无 commit。
