# Agent 工具调用默认账本与产物追踪收口

## 做了什么

- 普通 Agent 工具结果中的 `file_id/package_id/artifact_id/document_id/chunk_id/page/source_file_id` 会被轻量抽取为引用摘要，进入 `agent_message_meta.references`，同时保留在 `tool_events` 原始结果中。
- Agent runtime workflow link 在工具结果落账时，会把工具结果引用写入 `agent_tool_calls.result_ref.artifact_refs`，并额外创建 `agent_workflow_artifacts` 的 `tool_reference/tool_references` 记录。
- LLM/runtime 返回 error 但此前没有 workflow 时，会先创建 `agent_runtime` workflow，再写入 `agent_failure_records` 和 `agent_verification_results(runtime_exception=fail)`，避免无账本失败。
- Agent 前端工具卡片补齐最小可见性：展示工具进行中/完成/失败状态、失败原因、工具结果中的引用 ID。

## 改动范围

```text
modules/agent/backend/_utils.py
modules/agent/backend/runtime/workflow_link.py
modules/agent/backend/tests/test_workflow_runtime_link.py
modules/agent/frontend/index.vue
modules/agent/frontend/components/ToolCallCard.vue
modules/agent/frontend/components/WorkTraceGroup.vue
```

## 验证

```text
backend/.venv/bin/ruff check modules/agent/backend
backend/.venv/bin/python -m pytest modules/agent/sandbox/test_module.py -q
backend/.venv/bin/python -m pytest modules/agent/backend/tests/test_workflow_service.py modules/agent/backend/tests/test_workflow_api.py modules/agent/backend/tests/test_workflow_runtime_link.py -q
cd frontend && npm run build
```

结果：ruff 通过；sandbox 20 passed；workflow service/api/runtime 28 passed；frontend build 通过。

活系统验证：

- `agent:list_workflows` 通过 `/api/modules/call` 返回 200。
- 创建 `codex-agent-default-ledger-live-20260704` workflow 后，`agent:record_tool_call` 写入 `knowledge__search` 工具账本，HTTP 读取 `/api/agent/workflows/9/tool-calls` 可见参数摘要。
- `agent:record_verification(status=fail)` 写入失败验证，finalize 后 workflow 进入 `failed/failed_verified/fail`。
- 验证产生的 workflow run 9 及关联 tool_call/verification 已清理，清理后 `agent:list_workflows` 返回空列表。

## 残留风险

- 本轮不实现 ContentPackage publish，不读取 Knowledge/Content 表，只保留工具返回的引用 ID。
- 活系统真实 LLM 自主触发工具调用受模型输出影响，默认 runtime 链路用 `test_workflow_runtime_link.py` 覆盖；活系统用 Agent workflow capability 验证账本读写与失败可见。
- 收工时工作区存在其他并发/既有 dirty 文件，非本轮 Agent 收口改动，未回滚。
