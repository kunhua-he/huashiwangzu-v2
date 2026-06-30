---
name: "Agent底座维修09第二轮补修接手收尾"
type: task
tags: ["agent", "维修09", "补修", "completion_evidence", "trajectory", "ruff", "验收"]
created: 2026-06-30
agent: codex
---

接手 codex 中断后的 Agent 底座维修09第二轮补修。继续修复 completion evidence 在真实 runtime 事件缺少 tool_call_id 时返回空的问题：RuntimeTaskSink.generate_completion_evidence 保留 tool_call_id 精确关联，并新增按 call/result 顺序配对的兜底；读回验证必须存在可比较字段且匹配才置 True，避免空 comparable 导致假验证。补强 test_repair09.py：加入无 tool_call_id 的真实 runtime 事件形状，旧实现会 len==0 失败；保留唯一索引、record_turn upsert、rollback、预算、workflow、profile 等行为测试。额外限定在当前 Agent 变更文件内修复 ruff 导入排序/未用导入/变量名问题。

验证：工具台 run_test ../modules/agent/backend/test_repair09.py → 12 passed；真实库脚本验证 uq_trajectory_conv_turn 存在、record_turn 同 conv+turn upsert 返回同 id 且清理测试数据、无 tool_call_id evidence 生成 update evidence 且 read_back_verified=False；工具台 run_test ../modules/agent/backend → 130 passed；当前变更文件 ruff check → All checks passed。未提交 commit。
