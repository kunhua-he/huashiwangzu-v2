---
name: "dev_toolkit release_gate 发布门禁入口拆分"
type: "task"
tags: [dev-toolkit, release-gate, refactor, validation]
agent: "codex"
created: "2026-07-05T07:06:24.832365+00:00"
---

# 我是谁
codex

# 干了什么
将 `dev_toolkit/release_gate.py` 从 936 行大文件拆成兼容 CLI 入口 + `dev_toolkit/release_gate/` 子包：`context.py` 负责配置/共享状态/HTTP helper，`checks.py` 负责 health/system/queue/lifecycle/capability/readme/component/sandbox 检查，`smoke_gate.py` 负责 smoke/UI/model fallback 汇总，`printers.py` 负责结果和 RELEASE_GATE_JSON，`runner.py` 负责 argparse 与顶层流程，`__init__.py` 作为 import 兼容 facade。

# 验证了什么
`ruff check` 全绿；`pytest dev_toolkit/test_release_gate.py dev_toolkit/test_smoke_queue_gate.py dev_toolkit/test_module_sandbox_matrix.py` 为 68 passed / 1 skipped；`release_gate.py --preflight --skip-ui` 与 `--skip-ui` 均为 PASS_WITH_DEBT 且 blockers=[]；full gate 真实运行但当前 BLOCKED，原因是外部/current UI Playwright 失败 3 个（两个 401 session expired，一个 window snap preview）。

# 残留风险
当前共享工作区存在外部 frontend/tests 拆分 dirty 文件，full gate 的 Git debt 与 UI blocker 不属于本次 release_gate 结构拆分范围；本次未越界修改 frontend。

# 关联 commit
ffa08216 refactor: split release gate implementation
