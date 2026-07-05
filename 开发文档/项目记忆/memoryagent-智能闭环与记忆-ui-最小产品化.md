---
name: "MemoryAgent 智能闭环与记忆 UI 最小产品化"
type: "task"
tags: [memory, agent, frontend, evidence, workflow, closed-loop]
agent: "codex"
created: "2026-07-05T08:27:26.743873+00:00"
---

## 做了什么
- 将 Memory 前端从 stub 升级为最小产品化管理面：列表、语义/关键词搜索、详情元数据、删除、空态说明。
- 补齐 Memory 前端 api/types/composables，不使用 any/as any/@ts-ignore。
- Agent workflow evidence card 增加 memory_id 识别，显示来源模块 memory、ID、标题/摘要；WorkflowDetail 空态文案明确 evidence/reference 链路，不读 memory_* 表。

## 验证
- npm --prefix frontend run build 通过。
- backend/.venv/bin/python -m pytest modules/agent/backend/tests/test_workflow_service.py modules/agent/backend/tests/test_workflow_api.py：20 passed。
- PYTHONPATH=backend backend/.venv/bin/python modules/memory/sandbox/test_module.py：PASS。
- call_capability(memory save/list/recall/delete) 活系统通过，测试 marker 清理后 memory_records/memory_chunks 均为 0。
- call_capability(agent list_workflows) 200；/api/health ok。

## 残留风险
- 浏览器冒烟发现当前 dev 登录页未持久化 v2_auth_token 时，模块 runtime 会因 401 重定向登录；这是框架/登录持久化问题，未在本模块任务越界修改。
- 本轮工作区存在并发外部 dirty：dev_toolkit/smoke.py、dev_toolkit/test_smoke_queue_gate.py 和 image-gen 项目记忆，未纳入本提交。

## 关联 commit
- e870313b feat: productize memory closed loop UI
