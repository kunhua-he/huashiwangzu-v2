---
name: "Agent schema 去重与测试正常包导入修复"
type: task
tags: ["agent", "schema", "tests", "pytest", "router"]
created: 2026-06-29
agent: zcode
---

核实并修复 Agent schema 重复定义和测试收集问题：router.py 中 schema 从迁移中途遗留为内联定义，schemas.py 中 PromptItemCreate/PromptItemUpdate 缺 key 字段；同时 router.py 还保留 AgentConfigCreate/AgentConfigUpdate 重复定义。修复：schemas.py 补 PromptItemCreate.key 和 PromptItemUpdate.key；router.py 删除 CreateConvRequest/RenameConvRequest/UpdatePromptRequest/ApprovalDecision/PromptItemCreate/PromptItemUpdate/AgentConfigCreate/AgentConfigUpdate 内联类，统一从 .schemas import，并把 logger 放到 import 块之后。测试收集修复：新增 modules/agent/backend/conftest.py 统一设置 JWT_SECRET 和 sys.path；test_intent_preflight.py 改为正常包路径 import；test_model_client_inline_tool_calls.py 删除 sys.path/services + fake app.gateway importlib hack，改为正常导入 modules.agent.backend.services.model_client。验证：ruff check 覆盖 router/schemas/conftest/两个测试文件，All checks passed；pytest 两个测试文件正常收集并 10 passed；grep 确认 router.py 不再定义这些 schema 类。
