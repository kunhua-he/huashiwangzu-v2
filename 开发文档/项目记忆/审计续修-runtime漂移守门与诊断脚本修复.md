---
name: "审计续修-runtime漂移守门与诊断脚本修复"
type: task
tags: ["审计", "底座", "runtime", "工具脚本", "沙箱", "验证"]
created: 2026-06-27
agent: codex
---

# 改了什么

在上一轮审计清理基础上继续收口两个底座风险：

- 全仓 Python `F821`（未定义名）扫描已通过，确认此前修复的 `logger` / `io` / `Cm` / `_j` 是最后一批硬 NameError 风险。
- 修复 agent 诊断脚本：`modules/agent/tools/probe_raw_format.py`、`probe_toolcall_format.py` 的 backend 路径由 `parents[2]` 改为 `parents[3]`；`probe_raw_format.py` 不再导入已删除的 `_call_with_retry`，改为直接调用 `OpenCodeProvider.chat()` 保留原始响应探针价值。
- 修复 `modules/knowledge/sandbox/backend/main.py` 的模块 backend 路径计算，避免 sandbox 误找 `modules/knowledge/sandbox/backend/router.py`。
- 新增 `frontend/scripts/check-runtime-drift.js`，检查 `modules/*/runtime/index.ts` 与 `modules/_template/runtime/index.ts` 的漂移：15 个模块应保持模板字节级一致，12 个模块登记为已知变体；未知漂移会失败。
- `frontend/package.json` 新增 `npm run check:runtime-drift`；`modules/_template/README.md` 增加 Runtime Drift Check 说明。

# 验证了什么

- `find backend/app modules ... | xargs ruff check --select F821` -> All checks passed。
- `py_compile modules/agent/tools/probe_raw_format.py modules/agent/tools/probe_toolcall_format.py modules/knowledge/sandbox/backend/main.py` -> passed。
- `ruff check` 上述三个 Python 文件 `--select F401,F821,F841` -> All checks passed。
- `cd frontend && npm run check:runtime-drift` -> exact template copies 15, known variants 12, OK。
- `cd frontend && npm run build` -> passed。
- `cd backend && .venv/bin/python -m pytest tests/test_gateway_adapters.py tests/test_gateway_retry.py tests/test_opencode_provider.py tests/test_access_control_regressions.py tests/test_platform_workflow_ledger.py` -> 47 passed。

# 残留风险

runtime 仍是复制式架构；本次先加漂移守门，没有把 28 个 runtime 抽成共享包。后续若要彻底消除复制，应设计独立共享 runtime 包，而不是让生产模块直接 import `_template`。关联 commit：未提交。
