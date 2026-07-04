---
name: "Agent 工具调用默认账本与产物追踪收口"
type: "task"
tags: [agent, workflow, tool-ledger, artifact-ref, frontend]
agent: "codex-agent-default-ledger-r1"
created: "2026-07-04T10:24:47.844011+00:00"
---

# 改了什么
- 在 modules/agent/backend/_utils.py 增加工具结果引用 ID 抽取，普通 tool result 中的 file_id/package_id/artifact_id/document_id/chunk_id/page/source_file_id 会进入 Agent message references，同时原始 tool_events 保留。
- 在 modules/agent/backend/runtime/workflow_link.py 中，工具结果会把 artifact_refs 写进 agent_tool_calls.result_ref，并创建 agent_workflow_artifacts 的 tool_reference/tool_references 记录；runtime/model error 即使没有既有 workflow，也会创建 agent_runtime run 并写 failure + runtime_exception fail verification。
- 在 Agent 前端工具卡片中显示工具进行中/完成/失败、失败原因和工具结果引用 ID。
- 补充 test_workflow_runtime_link.py 用例，覆盖引用落账和无 workflow runtime failure 建账本。

# 验证了什么
- backend/.venv/bin/ruff check modules/agent/backend 通过。
- backend/.venv/bin/python -m pytest modules/agent/sandbox/test_module.py -q：20 passed。
- backend/.venv/bin/python -m pytest modules/agent/backend/tests/test_workflow_service.py modules/agent/backend/tests/test_workflow_api.py modules/agent/backend/tests/test_workflow_runtime_link.py -q：28 passed。
- finish_task 合跑 sandbox + workflow 三组测试：48 passed。
- cd frontend && npm run build 通过。
- 重启后端后，活系统 agent:list_workflows、create_workflow、record_tool_call、record_verification、finalize_workflow 验证通过；验证 run 9 及关联记录已清理，list_workflows 恢复为空。

# 是否还有残留风险
- 本轮不做 ContentPackage publish，不读取 Knowledge/Content 表，只保存工具返回的 ID 引用。
- 真实 LLM 自主触发工具调用受模型输出影响，默认 runtime 链路主要由 runtime link 单测覆盖；活系统验证覆盖 capability 账本读写与失败终态。
- 收工时工作区有大量非本轮 outside dirty（frontend/src、backend/app、dev_toolkit、knowledge/desktop-tools 与项目记忆），未回滚。

# 关联 commit
未提交。
