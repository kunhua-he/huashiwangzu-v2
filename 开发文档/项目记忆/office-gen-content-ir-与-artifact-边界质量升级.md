---
name: "office-gen Content IR 与 Artifact 边界质量升级"
type: "task"
tags: [office-gen, content-ir, artifact, module-boundary, quality]
agent: "codex-office-gen-worker-20260703-r1"
created: "2026-07-03T06:21:05.863695+00:00"
---

# 改了什么

- 仅修改 `modules/office-gen/**`：`README.md`、`backend/generator.py`、`backend/router.py`、`sandbox/test_module.py`、`tests/test_generator.py`。
- `generator.py` 兼容 Content IR 英文字段：`heading/paragraph/table/image/page_break`，并支持 `table_header/table_rows`、列对象、行对象和 PPTX `{name,elements}` 输入，避免 Content Export 调 office-gen 时生成空壳文件却成功。
- `router.py` 收紧能力边界：docx/xlsx/pptx/pdf/generate_to_artifact/replace_existing 要求格式对应的非空 content/sheets/slides；convert 改走 `read_uploaded_file`，复用框架 `check_file_access`、扩展名校验和路径穿越防护；generate_to_artifact/replace_existing 返回 `content_package_status/content_package_error`，不再把 Content Package 失败完全吞掉；export_to_artifact 先验文件权限，再查可访问 Content Package。
- README 更新为 8 个能力、Content IR/Artifact 接入边界、无副作用/有副作用验收命令和后续框架任务说明。

# 验证了什么

- `ruff check`：`modules/office-gen/backend/router.py`、`generator.py`、`tests/test_generator.py`、`sandbox/test_module.py` 全通过。
- `cd backend && .venv/bin/pytest ../modules/office-gen/tests/test_generator.py`：18 passed。
- `backend/.venv/bin/python modules/office-gen/sandbox/test_module.py`：docx/xlsx/pptx/pdf 真实生成校验全通过。
- `probe GET /api/office-gen/health`：200，`success:true`，LibreOffice 可用。
- `capabilities(module='office-gen')`：确认 8 个 capability 注册。
- `git diff --name-only -- modules/office-gen`：只有 5 个 office-gen 文件。

# 是否还有残留风险

- 没有运行会写入 live 数据的 `call_capability`，因此没有新增需要清理的文件/Artifact；真实写入链路由模块单测和无副作用 health 验证覆盖。
- `worktree_guard(module_key='office-gen')` 因共享工作区已有其他 agent 的 78 个外部 dirty 文件而返回 false；本次改动范围用 `git diff --name-only -- modules/office-gen` 单独确认合格。
- 如果产品希望 Content Package 解析失败时整个 artifact 操作失败，而不是返回 `content_package_status='failed'`，应作为后续框架 Content IR 策略任务处理，office-gen 不越界修改框架。

# 关联 commit

未提交。
