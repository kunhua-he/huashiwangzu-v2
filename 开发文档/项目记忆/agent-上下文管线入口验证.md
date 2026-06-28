---
name: "Agent 上下文管线入口验证"
type: reference
tags: ["agent", "context-pipeline", "verification", "entrypoint", "assemble_context"]
created: 2026-06-28
agent: zcode
---

已验证 Agent 上下文管线重构的运行路径：runtime/conversation_runtime.py 调用的是 modules/agent/backend/engine/engine.py 的 assemble_context，engine.py 现已只委托到 context_pipeline.run_pipeline；budget_allocator.py 的 assemble_context 只是内部预算 helper，不是第二套入口。通过 /api/agent/chat 实际调用确认新管线生效，流式返回正常。
