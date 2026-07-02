---
name: "frontend-runtime-cleanup节点1-入口工具台与API初筛"
type: "reference"
tags: [frontend, runtime, api-audit, worktree]
agent: "frontend-runtime-cleanup-worker"
created: "2026-07-02T16:05:47.605080+00:00"
---

节点1完成：已按任务要求读取 开发文档/README.md，并通过项目工具台执行 brief/plan_task/worktree_guard。CodeGraph/rg 初筛发现：1) frontend/src/shared/api/index.ts 是统一 Axios API，含 token 注入与统一响应解包；2) modules/*/runtime/index.ts 普遍存在 fetch/authHeaders/token 逻辑，这是模块 sandbox/runtime 独立 SDK 的系统性模式，不能用单点补丁随意替换；3) modules/knowledge/frontend/api.ts 有独立 fetch/token 封装，是优先核查的业务 API 冗余点；4) modules/agent/sandbox/src/App.vue 明确存在裸 fetch、手写 Authorization、catch(e:any)。工作区已有大量他人 backend/dev_toolkit/module 改动，后续只碰前端/runtime相关目标文件，不 revert 他人改动。
