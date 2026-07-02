---
name: "第二阶段底层深化审计节点-队列语义-Agent假绿-知识库与测试门禁"
type: "task"
tags: [audit, repair, node-checkpoint, agent, knowledge, taskqueue, testing, 20260702]
agent: "codex-conductor"
created: "2026-07-02T14:35:14.228438+00:00"
---

## 当前节点

用户要求继续深化底层审计，并强调子代理报告/阶段节点必须落盘，避免额度耗尽后丢上下文。本节点为第二阶段中途检查点。

## 主会话已完成并验证的修复

1. Knowledge `kb_pipeline` 文档行缺失不再制造 failed：
   - `modules/knowledge/backend/services/pipeline_service.py`
   - `doc is None` 现在返回 `status=skipped, reason=doc_missing, classification=obsolete`。
   - `_run_pipeline` 返回 `error` 但无 failed 状态时，外层显式归一为 `status=failed`，避免 `status=done + error` 的混乱语义。

2. Knowledge pipeline debt dry-run 扩展：
   - `modules/knowledge/backend/services/pipeline_debt_service.py`
   - 默认 File not found 分类同时覆盖 `Document % not found`，归入 `doc_missing/obsolete`。

3. Agent `profile_evolve` 解析失败软降级：
   - `modules/agent/backend/services/profile_evolve.py`
   - LLM 空响应/不可解析 JSON 返回 `status=skipped`，写 per-conversation watermark，不改用户画像，不污染 failed 队列。
   - `_parse_profile_json` 增强 fenced JSON、Python-style dict、字段归一。

4. Agent 事件持久化游标修复：
   - `modules/agent/backend/runtime/task_sink.py`
   - `persist_pending_events` 遇到第一条写入失败即停止推进，只推进连续成功前缀，避免中间失败事件被跳过。

5. Agent memory 后台任务假绿修复：
   - `modules/agent/backend/handlers/tasks.py`
   - `memory_distill` 返回 `ok/skipped/failed` 明确语义；gateway/memory save 失败会让 worker 判 failed；无事实可提取为 skipped。
   - `memory_dream` 空结果或 `success:false` 不再当 ok。

## 新增/更新测试

- `backend/tests/test_knowledge_pipeline_lifecycle.py`
  - doc_missing skipped
  - Document not found debt dry-run 分类
- `backend/tests/test_agent_profile_evolve_soft_failure.py`
  - 空 LLM/坏 JSON -> skipped + watermark
  - parser 接受 fenced/python-style dict
- `backend/tests/test_agent_task_semantics.py`
  - persist_pending_events 只推进连续成功前缀
  - memory_distill gateway/save failure 为 failed，无事实为 skipped
  - memory_dream 空结果为 failed

## 已验证

- Focused pytest：`18 passed`
  - `tests/test_agent_profile_evolve_soft_failure.py`
  - `tests/test_agent_task_semantics.py`
  - `tests/test_knowledge_pipeline_lifecycle.py`
  - `tests/test_task_worker_semantics.py`
- Ruff：受影响文件 `All checks passed!`

## 子代理已回来的关键结论

1. Memory/Profile explorer：
   - 旧 `No module named 'init_db'` 是历史债；当前代码无旧 import。
   - `profile_evolve` JSON 解析失败会污染 failed，主会话已修。

2. Knowledge explorer：
   - 主链路基本串通，但仍有阶段 HTTP 入口双路径风险、Prompt DB 未接入、IR 漏斗多标准、debt dry-run 无 apply。
   - 主会话先修运行时新 failed；Prompt DB 已派 worker。

3. Task Queue explorer：
   - 缺统一 governance dry-run/apply/archive API；不能直接清 failed 装绿。
   - 建议新增 `task_queue_governance_service`，后续专项做，不在当前半套实现。

4. Agent 主链路 explorer：
   - 双层 fallback 存在，Agent wrapper 和 gateway 都跑 fallback。
   - `persist_pending_events` 游标错位，主会话已修。
   - memory_distill/dream 假绿，主会话已修。

5. 测试门禁 explorer：
   - sandbox matrix 只跑 Python，不跑 frontend build，release gate 可能假绿。
   - smoke_all Agent 段实际没打 Agent。
   - health 对 completed 里的 semantic_failed 只统计不降级。

6. 模型 fallback explorer：
   - `fallback_chain.py` 确认仍在主链路。
   - 已派 worker 去按方案 A 去重：保留 wrapper 函数名，内部只调用 gateway 一次。

## 当前还在运行的子代理

- 假绿/吞错专项审计 explorer
- Project Toolkit MCP 修复 worker
- Knowledge Prompt DB 接入 worker
- Agent fallback 去重 worker

## 当前工作区注意

- 工作区 dirty，包含主会话改动和子代理通过 `memory_write/mcp_feedback` 生成的项目记忆文件。
- 不要回退这些未跟踪记忆文件。
- 后续每个节点继续 `memory_write` 落盘。
