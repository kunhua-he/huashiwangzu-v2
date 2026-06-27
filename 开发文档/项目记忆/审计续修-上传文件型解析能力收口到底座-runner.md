---
name: "审计续修：上传文件型解析能力收口到底座 runner"
type: task
tags: ["审计", "底座", "parser", "access-control"]
created: 2026-06-27
agent: codex
---

# 改了什么

- 新增 `backend/app/services/uploaded_file_runner.py`，统一上传文件型 capability 的 `file_id` 正整数校验、caller 用户解析、`check_file_access` 权限校验、扩展名白名单和安全路径解析。
- `backend/app/services/file_reader.py` 增加 `require_positive_file_id`，让 parser/file-aware 模块复用一致的参数校验。
- 迁移 `text-parser`、`markdown-parser`、`csv-parser`、`structured-parser`、`docx-parser`、`pdf-parser`、`pptx-parser`、`xlsx-parser`、`email-parser`、`image-vision` 到共享 runner；各模块解析算法保留在模块内。
- runner 在完成权限读文件后关闭 DB session，再执行解析/视觉模型调用，避免长时间解析占用连接。
- 为 `markdown-parser`、`csv-parser`、`structured-parser`、`email-parser` 增加最小 sandbox samples，并将它们纳入 parser 越权回归矩阵。

# 验证了什么

- `cd backend && .venv/bin/ruff check ...` touched Python files 通过。
- `cd backend && .venv/bin/python -m pytest tests/test_access_control_regressions.py` 13 passed。
- `cd backend && .venv/bin/python -m pytest tests/test_access_control_regressions.py tests/test_module_capability_drift.py` 14 passed。
- `python3 scripts/check-capability-drift.py` 通过，106 registered public capabilities。

# 是否还有残留风险

- 共享 runner 统一了 parser/image-vision 前置路径，风险集中在文件权限/路径读取公共层；已有越权矩阵覆盖主要 parser 与新增文本/结构化/邮件类 parser。
- 未改变各模块具体解析算法。

# 关联 commit

- 未提交。
