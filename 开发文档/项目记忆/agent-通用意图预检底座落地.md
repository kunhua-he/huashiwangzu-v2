---
name: "Agent 通用意图预检底座落地"
type: task
tags: ["agent", "intent-preflight", "precision-router", "experience", "sse"]
created: 2026-06-28
agent: zcode
---

完成 Agent 通用 Intent Preflight 底座：新增 runtime/intent_preflight.py，通过 DB prompt 驱动 cheap model 输出通用任务契约（task_category/answer_shape/evidence_policy/tool_strategy/risk_policy），不针对任何业务词硬编码；ConversationRuntime 在 SSE stream 内懒执行 preflight，先向前端发 thinking 占位，避免 HTTP 30s 阻塞；preflight 结果注入 system prompt 并记录 intent_preflight_diag。低置信/高风险且 verifier 要求 ask_clarification 时，直接流式输出追问，避免进入 ToolLoop 乱搜或编造。RuntimeTaskSink 保存成功经验时改用 user_input + intent_summary + task_category/answer_shape 作为 trigger，并记录 tools_used。验证：py_compile 通过；test_intent_preflight + test_prompt_service 共 8 passed；后端重启健康；真实流式请求验证会先发 thinking，再在证据不足时流式追问。注意：使用 project_toolkit probe 测 SSE 会 30s timeout，因为 preflight 两次 LLM 可能超过 probe 默认超时；用 Python urllib 流式客户端验证成功。
