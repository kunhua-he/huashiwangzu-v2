---
name: "收敛维修完成：release gate 与 runtime reset 收口"
type: "task"
tags: [convergence, release-gate, reset-runtime, ui-e2e, agent-board, github-push]
agent: "codex-convergence-repair"
created: "2026-07-03T17:20:45.010962+00:00"
---

# 改了什么

- 收敛 release gate：`release_response` 缺失 `RELEASE_GATE_JSON` 时 fail closed，返回 `INVALID_GATE_OUTPUT`；`PASS_WITH_DEBT` 不再映射 clean success。
- `release_gate.py` 增加 `--preflight`，只跑 health/system-status/queue baseline+audit/semantic scan/UI coverage 标记，不跑耗时 smoke/sandbox；`--skip-ui` 永远只允许 `PASS_WITH_DEBT` 或 blocker，不是 clean pass。
- MCP `release_gate` 增加 `mode=preflight|full`，默认 preflight；timeout 时 terminate/kill 子进程并返回结构化失败。
- `reset_runtime_data.py` 加固为显式 scope allowlist、dry-run 默认、apply 确认字符串、DB backup、本地 DB 和生产名保护、runtime 路径/symlink/backup-dir 防误删。
- `.gitignore` 忽略 `backend/backups/`，保留本地备份但不入仓。
- `frontend/tests/ui-e2e.spec.mjs` 修复 recycle restore：`/api/recycle/restore` 使用 recycle item id + `item_type`，不是原始 file id。
- 接管 stale `codex-conductor-sweep-20260703-r2`，并创建本轮 `codex-convergence-repair-20260704` 收口任务。

# 验证了什么

- `backend/.venv/bin/python -m pytest dev_toolkit/test_release_response.py dev_toolkit/test_release_gate.py dev_toolkit/test_server_helpers.py dev_toolkit/test_mcp_entry.py` -> 56 passed。
- `cd backend && pytest tests/test_reset_runtime_data.py` -> 9 passed。
- `backend/.venv/bin/python -m ruff check ...` -> All checks passed。
- `backend/.venv/bin/python dev_toolkit/release_gate.py --skip-ui --preflight` -> `PASS_WITH_DEBT`, `clean_pass=false`, `release_safe=true`。
- `backend/.venv/bin/python dev_toolkit/release_gate.py --skip-ui` -> `PASS_WITH_DEBT`, `release_safe=true`, sandbox 35/35 pass。
- `git check-ignore -v backend/backups/full/pre_cleanup_20260704_002527/database.sql` 命中 `.gitignore:40:backend/backups/`。
- `/api/health` 200 ok。
- UI 子代理验证 `5.2 File management - delete and recycle` Playwright 1/1 passed。

# 是否还有残留风险

未跑全量 `npm run test:browser`；本轮按收敛维修范围只验证了 delete/recycle 单场景和后端 release gate skip-ui。skip-ui 仍是 tracked debt，不是 clean release。

# 关联 commit

- `7777a736` converge release gate and runtime cleanup
