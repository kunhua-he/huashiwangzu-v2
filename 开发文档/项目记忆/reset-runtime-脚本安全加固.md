---
name: "reset runtime 脚本安全加固"
type: "task"
tags: [reset-runtime, maintenance, backend, safety, tests]
agent: "codex-convergence-reset-worker"
created: "2026-07-03T17:15:37.596061+00:00"
---

# 改了什么

- 将 `backend/scripts/maintenance/reset_runtime_data.py` 加固为默认 dry-run 的维护脚本；apply 必须传 `--yes` 与精确 `--confirm "RESET <db_name>"`。
- 新增 `--scope` 显式范围：`tasks`、`knowledge`、`agent`、`files`、`all-runtime`，截断表只来自固定 allowlist，缺失表进入 `skipped_tables`。
- apply 强制 `--db-backup` 指向已存在备份文件或包含 `database.sql`/`manifest.json` 的目录；默认拒绝非本地 DB host，拒绝含 prod/production/prd/生产的 DB 名。
- 文件清理要求 `--backup-dir`，并校验 runtime dirs 位于 `backend/data` 下、非 symlink、不是 repo/backend/backend-data 根；backup dir 不得位于要清理的 runtime dir 内。
- 新增 `backend/tests/test_reset_runtime_data.py`，用 monkeypatch/fakes 覆盖确认、生产库名、非本地 host、scope allowlist、dry-run、backup-dir、symlink、DB backup 缺失等场景。

# 验证了什么

- `cd backend && pytest tests/test_reset_runtime_data.py` -> 9 passed。
- `backend/.venv/bin/python -m ruff check backend/scripts/maintenance/reset_runtime_data.py backend/tests/test_reset_runtime_data.py` -> All checks passed。
- CodeGraph impact 显示脚本无其他索引文件依赖。

# 是否还有残留风险

- 当前工作区存在主代理/UI 子代理的 dev_toolkit、frontend、.gitignore 和文档 dirty 改动，本任务未触碰。
- 关联 commit：未提交。
