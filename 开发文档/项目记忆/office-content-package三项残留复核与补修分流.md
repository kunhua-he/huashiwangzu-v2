---
name: "Office Content Package三项残留复核与补修分流"
type: task
tags: ["office", "content-package", "audit", "migration"]
created: 2026-06-30
agent: codex
---

复核执行人自报三项：backend/app/models/office.py 已删除且 Base.metadata 无 file_json 表；所有 modules/*/runtime/index.ts 已无 previewPatch/applyPatch/RollbackResult/旧端点；backend/tests/test_office_json_patch_flow.py 真跑 4 passed，旧 preview/apply/rollback 活栈均 404，/api/office/status/1 活栈 200，前端 build 通过。发现小问题：测试文件 Ruff I001 import 顺序错误，已直接修复并复验 lint All checks passed、4 passed。发现大问题：真实 PostgreSQL 仍保留四张 framework_file_json_* 空表，历史 baseline/性能迁移仍会创建/引用，当前框架与底层 README 仍列为现役。未擅自 DROP；已写邮箱补修信《补修-Office-Content-Package旧表迁移与文档收口.md》，要求先确认0行，再新增 Alembic退役revision、全新库验证、文档收口。关联 commit：无。
