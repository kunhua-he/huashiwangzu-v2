---
name: "Agent工具指引与提示词分层自优化架构建议"
type: architecture
tags: ["agent", "prompt-control-plane", "skills", "tool-playbook", "workflow-recipe", "用户隔离", "自动优化"]
created: 2026-06-30
agent: codex
---

针对“不是沙箱限制，而是缺指向性工具/技能/流程”的诊断，建议不推倒重写，基于现有 agent_prompts(owner_id/scope/version)、agent_configs、agent_skill_registry(scope/version/allowed_tools)、agent_workflow_recipes(owner_id)、trajectory、ToolMetadata 建 Prompt/Skill Control Plane。分层：不可覆盖的全局安全/工具契约；全局基础工具指引；企业/岗位；agent_code 专属 overlay；owner_id 用户 overlay；会话/recipe。Agent 可修改自己 scope 内的 overlay/skill/playbook，不能直接改全局工具 schema、安全边界或扩大 allowed_tools；新增代码能力仍需模块开发。执行失败分类：能力缺失→新工具；能力存在但不会用→工具 playbook/发现策略；多工具固定链→skill/workflow；风格/选择偏好→prompt overlay；工具 bug→修工具。底座优化闭环：每轮记录实际 prompt/version/tool path/outcome/correction；定期生成候选 diff；离线 replay+留出集评估；管理员批准/自动阈值后小流量 canary；指标稳定再提升为 global base，保留版本回滚，禁止单个用户经验直接污染全局。当前 agent_skill_registry/agent_configs 缺 owner_id+agent_code 的完整绑定，建议新增 binding/candidate/evaluation 层，不把所有字段硬塞现表。
