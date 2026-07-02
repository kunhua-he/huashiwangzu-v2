---
name: "标准化邮箱投递信与回信五件套 MCP"
type: task
tags: ["mcp", "mailbox", "delivery-bundle", "dev-toolkit", "refactor"]
created: 2026-07-02
agent: codex
---

本次将邮箱投递信和回信五件套标准化进项目工具台 MCP：新增 mailbox_write_letter、mailbox_create_delivery_bundle、mailbox_check_delivery_bundle；旧别名 写封信 保留并转到标准格式。mailbox_write_letter 会自动补系统指令、必读文档、交付要求和收件箱路径；mailbox_create_delivery_bundle 固定生成 交付报告.md、修改文件清单.md、验收命令结果.md、剩余风险.md、元信息.json；mailbox_check_delivery_bundle 校验五件套和元信息必填字段。按用户反馈，拆出 dev_toolkit/mailbox_tools.py，server.py 从 3000+ 降到 2968 行。文档同步更新 AGENTS.md 与 dev_toolkit/README.md。验证：py_compile 通过；ruff 通过；git diff --check 通过；直接调用新工具生成测试投递信和测试五件套并 check 成功，测试产物已清理。残留：server.py 仍有 2968 行，下一轮建议继续拆 tool_catalog.py、memory_tools.py、worktree_tools.py。
