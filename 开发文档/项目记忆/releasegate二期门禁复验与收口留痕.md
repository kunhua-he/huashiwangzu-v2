---
name: "ReleaseGate二期门禁复验与收口留痕"
type: "task"
tags: [release-gate, contract, capability-drift, component-key]
agent: "codex-release-gate-contract-r1"
created: "2026-07-04T12:44:06.685596+00:00"
---

# 改了什么

执行《执行信-ReleaseGate二期能力漂移与文档矩阵门禁.md》。本轮确认 release gate 已覆盖 capability drift、README acceptance matrix、component_key contracts、sandbox chunk warning debt 与 compact summary 输出；在允许边界内补充了 `dev_toolkit/test_release_gate.py` 的三条测试：live 未声明能力为 BLOCKER、source 注册但 live 缺失为 BLOCKER、normal app component_key 文件缺失为 BLOCKER。

# 验证了什么

- `backend/.venv/bin/ruff check dev_toolkit/release_gate.py dev_toolkit/release_response.py dev_toolkit/module_sandbox_matrix.py`：通过，All checks passed。
- `backend/.venv/bin/python -m pytest dev_toolkit/test_release_gate.py dev_toolkit/test_release_response.py`：通过，40 passed, 1 skipped。
- `backend/.venv/bin/python -m pytest dev_toolkit/test_release_gate.py dev_toolkit/test_release_response.py dev_toolkit/test_module_sandbox_matrix.py`：通过，58 passed, 1 skipped。
- `release_gate(skip_ui=true, mode=preflight)`：返回 BLOCKER，证明新门禁在活栈可工作；Capability drift PASS，README acceptance matrix DEBT，Component key contracts BLOCKER，compact_summary 已含 verdict/blockers/debts/clean_release_ready/deploy_allowed。

# 残留风险

活栈 BLOCKER 来自真实存量模块契约问题：`terminal-tools` 与 `web-tools` 为 background-service 但仍有非空 `component_key`。`modules/` 在本执行信禁止边界内，本轮只记录不修。README acceptance matrix 仍有 28 个模块缺失，为后续独立文档任务。

# 关联 commit

未提交。
