---
name: "W2 docs-open token scope 与文件写权限修复"
type: "task"
tags: [docs-open, access-control, token-scope, file-permission, regression-test]
agent: "codex-w2"
created: "2026-07-02T11:38:53.619917+00:00"
---

W2 修复 docs-open 写权限与 token scope：新增 framework check_file_write_access（owner 或 share permission=edit），replace_file_content 改用当前 user_id 做写 ACL；docs-open content 写入不再用 file.owner_id/admin 伪装调用者；content/export/revoke/open(edit)/embed(edit) 改用写权限；token scope 支持 doc_ids(read) 与 edit_doc_ids(edit)，content/raw file token 路径执行 check_doc_access；revoke 只撤销 scope 包含目标 file_id 的 token。新增 test_docs_open_write_requires_file_edit_access 与 test_docs_open_token_scope_enforced_for_content_file_and_revoke。验证：ruff 7 个改动文件通过；pytest backend/tests/test_access_control_regressions.py 15 passed；/api/health ok。工作区有其他会话改动，W2 只改允许范围文件。
