---
name: "Agent 上下文管线重构设计"
type: architecture
tags: ["agent", "context-pipeline", "reducer", "injector", "workflow", "experience", "compression", "docs"]
created: 2026-06-28
agent: zcode
---

完成 Agent 上下文管线重构设计文档，核心结论是把当前 assemble_context 拆成 project_history / reduce_context / inject_context_layers / assemble_context 四层管线；工具结果压缩采用规则优先、LLM 兜底；成功经验升级为 workflow recipe（流程建议）而非原始数据回放；context_vars、workflow_strategy、experience_memory 都应变成独立 injector。文档已写入 开发文档/项目记忆/agent-context-pipeline-refactor-design.md 并更新 _索引.md。
