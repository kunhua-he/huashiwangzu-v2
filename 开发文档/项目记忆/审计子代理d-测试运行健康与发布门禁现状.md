---
name: "审计子代理D-测试运行健康与发布门禁现状"
type: "task"
tags: [audit, health, release-gate, tests, ui-e2e, queue-debt]
agent: "codex-audit-subagent-d"
created: "2026-07-03T16:18:16.211389+00:00"
---

只读审计测试/运行健康和发布门禁现状。证据：/api/health 200 status=ok db=ok worker running，但 task_queue failed=892 historical_failed_debt=892；/api/system/status backend/db/worker/model_service/entry 均 true。release_gate(skip_ui=true) returncode=0 verdict=PASS_WITH_DEBT，9 PASS/4 DEBT，债务含 smoke UI skipped、queue failed=892/pending=1/completed=1591、historical debt=890、recent failed=2，sandbox matrix 35/35 pass。smoke_all(skip_ui=true) 29 total/28 passed/0 failed/1 skipped(UI)，并清理测试文件；队列无新增失败。随后真实 cd frontend && npm run test:browser：36 tests 中 35 passed、1 failed，最终报告因 5.2 File delete+recycle failed：Deleted=false, in recycle=false；运行后 /api/tasks/worker/status failed 从 892 到 893，audit recent_failed=3。frontend npm run build passed，但有大 chunk warning。关键 pytest：test_framework_health 7 passed，test_task_queue_audit 14 passed，test_module_boundary_contracts 10 passed。ruff lint release_gate/smoke/module_sandbox_matrix passed。风险：发布门禁 skip-ui 时不能代表 UI 可发布；后端历史债务仍大，kb_pipeline failed 757，top signatures File not found 703、profile_evolve No module named init_db 130、Parser returned no content blocks 16；completed_semantic_failures=217 需人工复核。测试可信度：smoke 已用内层 success 判断和队列 delta，但仍跳过 UI 时只给 PASS_WITH_DEBT；pytest 中存在大量 source-level/read_text 字符串断言，只适合结构护栏，不能替代运行态测试。
