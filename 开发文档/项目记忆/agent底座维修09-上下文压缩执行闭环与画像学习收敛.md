---
name: "Agent底座维修09 — 上下文压缩执行闭环与画像学习收敛"
type: task
tags: ["agent", "上下文压缩", "预算", "轨迹", "画像收敛", "完成证据", "SystemTaskQueue", "workflow_mine"]
created: 2026-06-30
agent: opencode
---

## 执行 Agent

opencode

## 做了什么

4 批修复：
1. **上下文软预算 & 压缩**：新增 `get_effective_context_budget()` 统一口径（null→48k）；`_compress_context()` 不再因 budget=None 跳过；Stage 5 估算全量 projected messages；assembler 改为"最新优先"。
2. **工具循环预算守卫**：每轮模型调用前执行 budget guard 裁历史（保留 system + 最新多轮 + 完整工具对）；usage 新增 `model_call_count`/`max_single_call_prompt_tokens`。
3. **持久化闭环**：`record_turn()` upsert 幂等；`run_post_turn_hooks()` 改为 SystemTaskQueue 投递（删除 create_task 路径）；注册 `workflow_mine` handler；`run_mining_job` 改用 `recipe_match_score` 语义分组。
4. **画像收敛 + 完成证据**：profile_evolve 增量分析→信号池→阈值门控→LLM 归并→字段上限；新增 `COMPLETION_VERIFICATION_KEY` prompt；`generate_completion_evidence()` 扫描 tool_events。

## 改了哪些

13 文件全部在 `modules/agent/backend/` 内：
- engine/: budget_allocator, context_pipeline, compressor, workflow_recipe_service
- runtime/: task_sink, tool_loop_runtime
- services/: profile_evolve, trajectory_service
- handlers/: tasks, bootstrap, models, init_db, prompt_seeds

## 验证

- Agent 单测 118/118 passed
- Smoke 26/26 全绿
- 活系统 health/agent-health ok
- `workflow_mine` 已注册到 worker handlers

## 遗留

- memory stable rule 3 条重复数据未处理（memory 模块任务）
- owner 4 生产画像修复未执行（需验收人确认后单独执行）
