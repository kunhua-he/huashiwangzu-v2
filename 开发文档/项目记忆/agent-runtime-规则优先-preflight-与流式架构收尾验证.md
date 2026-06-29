---
name: "Agent runtime 规则优先 preflight 与流式架构收尾验证"
type: task
tags: ["agent", "runtime", "intent-preflight", "rule-first", "streaming", "verification"]
created: 2026-06-29
agent: zcode
---

本轮继续完成 Agent runtime 收尾验证：修复 IntentPreflight 规则优先实现的测试收集环境变量问题和 ruff 收尾问题；确认规则优先 preflight 默认不调用 LLM、不短路普通问题，只注入紧凑路由提示；确认 tool-call streaming accumulator、StreamProxy、前端 provisional MessageBubble、skill role/effective action policy、experience save metadata 等改动仍可验证。验证：`pytest modules/agent/backend/test_intent_preflight.py backend/tests/test_gateway_tool_call_accumulator.py` 实际以绝对路径运行，11 passed；`ruff check` 覆盖本批 Python 改动，All checks passed；`npm --prefix frontend run build` 通过，仅有既有 chunk size warning。当前尚未提交，工作区包含产品代码/测试/文档变更以及运行时数据噪声文件，提交时建议排除 backend/data/agent/*.json、dev_toolkit/memory_embeddings.json 等运行态变更，按功能拆成 streaming + rule-first preflight 两个提交。
