---
name: "Agent 已工作时间线：保留中途回复草稿"
type: task
tags: ["agent", "timeline", "assistant-draft", "experience"]
created: 2026-07-02
agent: opencode
---

## 改动

LLM 中途回复用户的草稿文本不再彻底丢弃。被 rollback/replace 的中途文本作为 `assistant_draft` 类型持久化到 timeline，默认折叠展示在"已工作"组件中。

### 后端改动

- `modules/agent/backend/runtime/tool_loop_runtime.py`:
  - `_stream_until_tool_or_done()`: 三处 rollback（tool_call_detected、inline_tool_call_detected、unfinished_tool_intent）均先保存 `content_parts` 为 `assistant_draft` 再 clear
  - `_generate_final_summary()`: summary_cleaned 场景保存原文本为 `assistant_draft`

- `modules/agent/backend/runtime/stream_emitter.py`:
  - `yield_final_stream()`: inline_calls 和 unfinished_tool_intent 场景保存 `full` buffer 为 `assistant_draft`

### 前端改动

- `modules/agent/frontend/index.vue`:
  - `rollbackAssistantStream()`: 移除 streaming message 前捕获内容，追加到当前工作组的 `assistant_draft`
  - `replace` SSE 事件: 替换前保存 `streamingText` 为 draft
  - `expandTimeline()`: 刷新后渲染 `assistant_draft` timeline 条目到工作组

- `modules/agent/frontend/components/WorkTraceGroup.vue`:
  - 新增 `assistant_draft` 渲染：显示"回复用户"标题、reason 标签、可展开/折叠
  - 样式：轻量气泡，默认折叠，展开显示原文

### 持久化与上下文隔离

- `assistant_draft` 通过 timeline 持久化（复用 `sink.persist_assistant` 的 timeline 字段），不新建表
- `assistant_draft` 不进 `messages` list，自动排除在 LLM 上下文之外
- 刷新后以服务端 timeline 为准渲染

### 去重

- 前端 streaming draft 通过 segment_id 推入工作组；后端最终 timeline 也包含同一条 draft
- 刷新后以服务端 timeline 为准，前端 streaming draft 随工作组重置自然消失

### 测试

- `test_assistant_draft.py` 7 项：draft 追加逻辑、空 draft 跳过、unfinished_tool_intent、LLM 上下文隔离、多段顺序、proxy rollback 闭包
