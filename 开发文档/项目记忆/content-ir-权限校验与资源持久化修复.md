---
name: "Content IR 权限校验与资源持久化修复"
type: "task"
tags: [content-ir, security, resource, worker-a]
agent: "parallel-repair-worker-a-codex"
created: "2026-07-02T10:31:13.694872+00:00"
---

Worker A 修复 Content IR 安全与资源持久化：1) content:write_ir 支持 source_file_id/file_id，并在 write_ir 服务层用 app.services.file_service.check_file_access(db,file_id,user_id) 做 owner/share 校验，system principal 仍由 capability 层拒绝；2) document/presentation/text/mixed 写 ContentPackage 时保留 metadata/resources，并将 data_b64 资源落到 Resource 后把 block.resource_ref 映射为真实 resource_id，同时写 ResourceRef；3) content:store_resource(file_id) 和 store_analysis_resource 统一走框架 check_file_access，store_resource 先校验再落资源；4) ResourceService.add_ref 改幂等，ContentPackageService.get_resource 遍历所有 ResourceRef，避免全局去重资源只看第一条 ref 导致归属误判。验证：ruff 5 文件通过；backend/tests/test_content_ir_architecture.py::TestWriteIR 10 passed；backend/tests/test_content_ir_architecture.py 42 passed；/api/health ok；测试残留查询为 0。未提交 commit。
