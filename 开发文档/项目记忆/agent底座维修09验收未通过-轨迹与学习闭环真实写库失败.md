---
name: "Agent底座维修09验收未通过-轨迹与学习闭环真实写库失败"
type: task
tags: ["agent", "验收", "trajectory", "SystemTaskQueue", "workflow_mine", "context_budget", "completion_evidence", "profile_evolve", "假绿"]
created: 2026-06-30
agent: codex
---

2026-06-30 对维修09执行零信任验收，结论不通过。真实 PostgreSQL 调用 record_turn 因 SQLAlchemy text 中 :param::jsonb 残留冒号报 PostgresSyntaxError，且异常未 rollback 导致同 session 后续 post-turn hooks 失效；uq_trajectory_conv_turn 迁移使用 PostgreSQL 不支持的 ADD CONSTRAINT IF NOT EXISTS，数据库实际无唯一约束；turn_index 错用 model_call_count；workflow miner 将 AgentTrajectoryRecord 传给 recipe_match_score 触发 AttributeError；预算 estimate_one_message 忽略 tool_calls arguments，48k 诊断严重低估；completion evidence 可在 read 失败时仍 verified；profile 低信号不推进水位，会重复消费同一证据。旧 118 tests 通过但新增关键字在测试中 0 命中，smoke 26/26 的 Agent 段仅调用 memory overview_stats，未覆盖 chat 主链。已投递补修信：/Users/hekunhua/Documents/Agent/PHP/华世王镞_v2邮箱/投递箱/Agent底座维修09-验收退回补修-第1次.md。暂不投递下一阶段升级信。
