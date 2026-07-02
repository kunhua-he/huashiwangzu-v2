---
name: "审计修复：底座安全边界与 release gate 假绿收口"
type: "task"
tags: [audit-fix, dev-toolkit, knowledge, content-ir, agent, release-gate]
agent: "codex"
created: "2026-07-02T11:10:06.479699+00:00"
---

# 改了什么
- Content IR：修复 write_ir 基于 file_id 的越权写入风险，按 source_file_id + owner_id 定位包，写入前校验文件 owner/share 和编辑权限；补 mixed/document/text/presentation 资源持久化和 ResourceRef 幂等引用。
- dev_toolkit：新增 SQL 只读守卫并强制 psql 只读事务；release_gate/smoke 输出机器 JSON，区分 PASS/PASS_WITH_DEBT/BLOCKER，不再把 skipped/debt 映射成干净 PASS。
- Agent：对齐 terminal-tools__exec 敏感动作策略名，审批队列保留脱敏 tool_args；single-pass streaming 未完成 tool intent 增加 retry/degrade，不再直接 error break。
- Knowledge/file lifecycle：新增 file.deleted/file.restored 事件；knowledge 删除时暂停源文件不可用管线，还原时补入队；kb_pipeline 遇到 source_file_deleted/missing 返回 skipped，不污染 failed 队列，active 文件磁盘缺失仍 failed。
- Smoke：A5 recycle 改用 .bin 避免测试回收站时触发 knowledge 业务管线；Z1 异步队列改为新增 failed 零容忍。
- MCP wrapper：新增 release_response helper，锁定 PASS_WITH_DEBT => success=false/clean_pass=false/release_safe=true，避免工具台顶层字段假绿。

# 验证了什么
- py_compile 目标文件通过。
- ruff 目标文件 All checks passed。
- pytest：knowledge lifecycle/task worker/recycle/ingest/task queue 18 passed，dev_toolkit 27 passed/1 skipped，release_response/smoke queue 3 passed。
- MCP run_test：backend/tests/test_knowledge_pipeline_lifecycle.py + test_task_worker_semantics.py 3 passed。
- MCP release_gate(skip_ui=true)：脚本输出 PASS_WITH_DEBT；Health/System PASS；gate-run failed delta baseline=785 current=785，无新增失败。

# 残留风险
- 当前 MCP server 进程可能仍加载旧 server.py，需重启 MCP 后顶层 success/verdict 字段才会使用 release_response 新逻辑；在此之前以 RELEASE_GATE_JSON 为准。
- 历史 failed 队列债、recent failed debt、sandbox skipped debt 仍保留为债务，不清表伪绿。

# 关联 commit
- 尚未提交。
