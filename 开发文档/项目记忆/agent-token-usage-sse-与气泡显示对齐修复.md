---
name: "Agent token usage SSE 与气泡显示对齐修复"
type: task
tags: ["agent", "token-usage", "sse", "frontend", "runtime"]
created: 2026-06-29
agent: zcode
---

修复 Agent 回答气泡 token 显示与后端返回不对齐：现场排查发现旧事件中最终 assistant_msg 只有 content，没有 usage；ToolLoopRuntime 只在 `_accumulated_usage.total_tokens` 存在时下发 `round_usage`，导致最终回答走 `emitter.usage_data` 的场景会持久化/实时显示丢 token。修复为：后端统一 `_merge_usage/_has_token_usage`，final persist 使用完整 `_usage` 下发 `round_usage`，assistant_msg 事件 payload 同步带 usage；前端新增 `normalizeUsagePayload` 和 `attachUsageToLatestAssistant`，兼容 `usage`/`round_usage` 晚于 `assistant_stream_commit` 到达时补挂到最后助手气泡，并补齐 UsageData token 类型。验证：ruff tool_loop_runtime passed；聚焦 pytest 11 passed；frontend build passed；重启 backend 后 SSE smoke 出现 `round_usage`，示例 usage={prompt_tokens:7436, completion_tokens:192, total_tokens:7628, work_duration_ms:19796}；DB agent_events 最新 assistant_msg payload 已含 usage。
