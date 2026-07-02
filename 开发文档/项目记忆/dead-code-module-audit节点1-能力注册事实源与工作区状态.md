---
name: "dead-code-module-audit节点1-能力注册事实源与工作区状态"
type: "task"
tags: [dead-code, audit, module-registry, manifest, worktree]
agent: "dead-code-module-audit-worker"
created: "2026-07-02T16:05:14.278117+00:00"
---

节点1完成：已按 AGENTS 先读 开发文档/README.md，并通过项目工具台 brief/plan_task/worktree_guard 开工。CodeGraph 确认后端跨模块唯一入口为 backend/app/services/module_registry.py 的 register_capability/call_capability/list_capabilities，/api/modules/call 运行时以注册表为准，manifest public_actions 只是声明元数据。当前工作区已有 149 个 dirty/untracked 条目，来自多名 worker，后续审计以只读优先，不 revert 他人改动。日志尾部显示近期 smoke/capability 调用链路多为 200；image-vision 曾遇到 MiMo 401 后本地降级成功，暂不归为 module capability 声明问题。
