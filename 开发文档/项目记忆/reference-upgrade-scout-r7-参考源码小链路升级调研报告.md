---
name: "reference-upgrade-scout-r7 参考源码小链路升级调研报告"
type: "reference"
tags: [reference-upgrade-scout-r7, reference_sources, mcp, agent, knowledge, content-ir, investigation, 20260703]
agent: "reference-upgrade-scout-r7"
created: "2026-07-02T18:09:29.503980+00:00"
---

# reference-upgrade-scout-r7 参考源码小链路升级调研报告

边界：只做调研，不改项目代码。已读 `开发文档/README.md`，并使用项目工具台 `brief`、`plan_task`、`worktree_guard`、`code_explore`、`tail_log`、`memory_search`、`capabilities`、`routes`、`db_schema`。参考源目录为 `/Users/hekunhua/Documents/Agent/reference_sources`，未新增下载。

## 参考源码证据

- Hermes `tools/registry.py`：工具自注册、toolset、check_fn TTL、registry generation、dynamic_schema_overrides、拒绝非显式 override 的 tool shadowing。
- Hermes `cron/scheduler.py`：per-job enabled_toolsets 与 MCP server allowlist 合并，避免子场景工具白名单误删 MCP 工具。
- OpenHands `event_service_base.py` / `event/README.md`：conversation event 存储、过滤、分页、trajectory export 和流式事件服务分层。
- LangGraph `langgraph_sdk/schema.py`：Thread/Run 状态、disconnect_mode、multitask_strategy、stream_mode、checkpoint、interrupt 的小型状态词表。
- Microsoft GraphRAG `query/context_builder/local_context.py`、`api/query.py`、`utils/api.py`：local/global search 的 context_data 标准化，entities/relationships/claims/sources 分组返回，token budget 下拼 context 表。
- Docling `datamodel/base_models.py`：ErrorItem、page_no/bbox/confidence、PageConfidenceScores/ConfidenceReport，把解析质量从 bool 状态升级为可聚合画像。

## 1. Capability Registry 元数据升级：generation + availability + toolset 语义

本项目落点：
- `backend/app/services/module_registry.py`
- `modules/agent/backend/engine/tool_orchestrator.py`
- `modules/agent/backend/runtime/tool_gate.py`
- `modules/agent/backend/services/tool_discovery.py`
- `dev_toolkit/capabilities` 与 `release_gate`

小任务：`capability-registry-generation-worker-r7`

任务说明：借鉴 Hermes registry，把本项目能力注册表从“列表元数据”升级成可缓存、可审计、可分场景裁剪的能力目录。

验收范围：
1. `register_capability/unregister_capability` 维护单调递增 `generation`。
2. `list_capabilities(role=...)` 返回 `generation`、`read_only/side_effect/destructive/concurrency_safe`、`availability`，保持旧字段兼容。
3. Agent `determine_tool_metadata` 优先消费 capability 元数据，减少名字猜测。
4. `tool_gate` 拒绝未知或不可用工具时返回可诊断原因。
5. 测试覆盖 manifest/register/list/tool_gate 一致性，不改模块业务逻辑。

## 2. Agent Event/Trajectory 导出小闭环：paged event search + trajectory zip/json

本项目落点：
- `modules/agent/backend/engine/event_store.py`
- `modules/agent/backend/services/trajectory_service.py`
- `modules/agent/backend/router.py`
- `modules/agent/frontend/admin/*` 或现有治理面板
- 表：`agent_events`、`agent_trajectory_records`

小任务：`agent-trajectory-export-worker-r7`

任务说明：不重写 agent runtime，只在现有事件和轨迹上补 OpenHands 式查询/导出闭环。

验收范围：
1. 新增只读服务：按 `conversation_id`、`event_type`、`since_id`、`limit` 查询 `agent_events`，`id` 作为 cursor。
2. 新增 trajectory export：把 `agent_events` + `agent_trajectory_records` 组合为 JSON，可选 zip。
3. admin 端能下载单会话轨迹；viewer 只能导出自己的会话。
4. 不改变 SSE 行为；不新增并行事件解释器。
5. 测试覆盖分页、owner 边界、空会话、事件顺序。

## 3. Agent 运行状态词表收口：disconnect/multitask/cancel/interrupt

本项目落点：
- `modules/agent/backend/runtime/tool_loop_runtime.py`
- `modules/agent/backend/runtime/task_sink.py`
- `modules/agent/backend/handlers/tool.py`
- `modules/agent/frontend/index.vue` 与工作 trace 组件

小任务：`agent-run-state-contract-worker-r7`

任务说明：借鉴 LangGraph 的小词表，不引入 LangGraph；把长任务/断线/用户二次输入的行为显式成契约。

验收范围：
1. 定义 `AgentRunStatus = pending/running/error/success/timeout/interrupted`。
2. 定义 `multitask_strategy = reject/interrupt/rollback/enqueue`，先默认 `reject`，不改变现有行为。
3. SSE 首包/结束包携带 `run_status` 和 `disconnect_mode`。
4. UI 在已有“已工作”里显示 interrupted/timeout/error 的一致状态。
5. 测试覆盖断线继续、重复提交被拒绝、timeout 标记，不要求实现排队。

## 4. Knowledge Search Context Data 标准化：结果 + 证据分组返回

本项目落点：
- `modules/knowledge/backend/router.py`
- `modules/knowledge/backend/services/search_service.py`（或当前检索服务实际文件）
- `modules/knowledge/backend/services/graph_service.py`
- `modules/knowledge/frontend/api.ts`
- `modules/agent` 调 knowledge 的上下文注入处

小任务：`knowledge-context-data-worker-r7`

任务说明：借鉴 GraphRAG `reformat_context_data`，让 `knowledge:search` 除 `results` 外稳定返回 `context_data`，给 Agent 可解释引用。

验收范围：
1. `knowledge:search` 返回 `{results, context_data}`，`context_data` 固定含 `chunks/pages/entities/relationships/sources/claims`，缺失为空数组。
2. 每条 result 带 `source_type`、`document_id`、`page`、`block_id`、`score`。
3. 兼容旧前端只读 `results`。
4. Agent 调 knowledge 时优先注入 context_data 的 sources/chunks，不直接拼散文本。
5. 测试覆盖空结果、只有 chunk、带实体图谱三种返回。

## 5. Parser/Content IR 质量画像：page confidence + degraded reason

本项目落点：
- `backend/app/schemas/parser.py`
- `backend/app/services/content/ir_schema.py`
- `backend/app/services/content/ir_validator.py`
- `modules/knowledge/backend/services/raw_collection_service.py`
- `modules/knowledge/backend/services/fusion_service.py`
- parser 模块：`modules/pdf-parser`、`docx-parser`、`pptx-parser`、`xlsx-parser`、`text-parser`

小任务：`parser-quality-profile-worker-r7`

任务说明：借鉴 Docling 的 ErrorItem / ConfidenceReport，把“解析成功/失败”升级为可诊断质量画像，但不引入 Docling 依赖。

验收范围：
1. `ParseResult` 增加可选 `metadata`：`parser_version`、`quality_report`、`errors`、`degraded_reason`。
2. `quality_report` 支持总分和按页 `parse/layout/table/ocr` 分数；未知为 null，不伪造。
3. Content IR block `data` 允许 `source_span/page_no/bbox/confidence`，validator 只做结构校验。
4. knowledge raw/fusion diagnostics 持久化 degraded reason，并在 dashboard/stuck 分类里可见。
5. 先覆盖 2 个 parser（text + pdf/docx 任选一个），其他 parser 保持兼容空 metadata。

## 不建议本轮做

- 不建议重做 private modules、upload session、durable board：当前工作区已有相关改动在路上。
- 不建议直接引入 GraphRAG/Docling/LangGraph 作为运行时依赖；本项目已有明确模块边界，适合吸收小契约。
- 不建议改 terminal-tools 的隔离模型，项目规则已定。

## 验证/状态

只读调研，无代码改动。工具台 `tail_log` 返回空；`worktree_guard` 显示当前工作区已有 30 个未提交条目，其中本 agent 只新增开工/完成记忆与反馈记录。
