---
name: "审计续修-能力注册双轨漂移守门与memory SQL参数化"
type: task
tags: ["审计", "模块能力", "manifest", "register_capability", "memory", "SQL参数化", "底座"]
created: 2026-06-27
agent: codex
---

# 改了什么

针对审计报告中的“能力注册双轨制”风险，确认项目规则为运行时 `register_capability` 权威、manifest `public_actions` 为对外声明元数据，因此本次没有删除 manifest 声明，而是做了对齐和守门：

- 新增 `scripts/check-capability-drift.py`，用 AST 解析 `modules/*/backend/**/*.py` 中的 `register_capability(...)`，并对比 `modules/*/manifest.json` 的 `public_actions` action 名与 `min_role`。
- 支持 agent 模块的 `capabilities = [(module, action, ..., min_role)]` + for-loop 注册模式；如果出现无法静态解析的动态注册且没有可解析清单，脚本会失败。
- 新增 `backend/tests/test_module_capability_drift.py`，把能力漂移检查纳入 pytest。
- 对齐 manifest 元数据：
  - `image-gen:usage_history` 从 viewer 对齐到 runtime/editor。
  - `office-gen:docx/xlsx/pptx/pdf` 从 viewer 对齐到 runtime/editor（这些能力会写文件）。
  - `knowledge` 补声明 runtime 已注册的 `export`。
  - `memory` 补声明 runtime 已注册的 `recall_stable_rules` / `recall_chunk` / `save_stable_rule`。
- 顺手修复审计中发现的底层 SQL 风险：`modules/memory/backend/services/capabilities.py` 的 chunk 向量检索不再用 f-string 拼 vector literal，改为 `CAST(:query_vec AS vector)` 参数绑定。
- 清理 `modules/memory/backend/services/capabilities.py` 顶部未使用模型 import。

# 验证了什么

- `python3 scripts/check-capability-drift.py` -> `[capability-drift] OK (106 registered public capabilities)`。
- `cd backend && .venv/bin/python -m pytest tests/test_module_capability_drift.py tests/test_memory_core_paths.py` -> 39 passed。
- `backend/.venv/bin/ruff check modules/memory/backend/services/capabilities.py backend/tests/test_module_capability_drift.py scripts/check-capability-drift.py --select F401,F821,F841` -> All checks passed。
- `cd frontend && npm run check:runtime-drift` -> OK。
- `cd frontend && npm run build` -> passed。

# 残留风险

manifest 仍然是元数据副本，但现在有自动漂移守门。脚本只覆盖静态可解析的公共模块注册；私有模块动态注册和运行时按 owner_id 注入的能力不纳入本次检查。关联 commit：未提交。
