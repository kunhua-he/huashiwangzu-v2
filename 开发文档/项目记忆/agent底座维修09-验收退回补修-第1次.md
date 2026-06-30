---
name: "Agent底座维修09-验收退回补修-第1次"
type: task
tags: ["agent", "维修09", "补修", "trajectory", "upsert", "budget", "compressor", "profile_evolve", "completion_evidence", "workflow_mine"]
created: 2026-06-30
agent: opencode
---

## 执行 Agent

opencode

## 验收退回补修完成

修复 10 项 P0/P1 缺陷：

- **P0-1/4**: record_turn() 用 pg_insert() 替代 ::jsonb 文本, 异常回滚
- **P0-2**: init_db 用唯一索引替代 ADD CONSTRAINT IF NOT EXISTS
- **P0-3**: turn_index 用 DB event 计数替代 model_call_count
- **P1-1**: run_mining_job 拆出 _text_intent_similarity 纯文本函数
- **P1-2**: 新增 check_tool_success() 统一判定
- **P1-3**: estimate_one_message() 完整计入 tool_calls
- **P1-4**: _find_tool_pairs() 按 tool_call_id 配对
- **P1-5**: generate_completion_evidence() 关联 call+result
- **P1-6**: profile_evolve 指纹去重 + 排序 cap

## 验证

- Agent 单测 130/130 (118 旧 + 12 新增行为测试)
- 分支: codex/repair-agent-foundation-09-r1
