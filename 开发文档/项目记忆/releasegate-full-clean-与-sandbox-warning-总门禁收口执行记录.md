---
name: "ReleaseGate Full Clean 与 Sandbox Warning 总门禁收口执行记录"
type: "task"
tags: [release-gate, sandbox, dev-toolkit, smoke, model-fallback]
agent: "codex-release-gate-sandbox-warning"
created: "2026-07-04T14:33:16.085190+00:00"
---

## 改了什么
- 收口 ReleaseGate 最终 verdict 语义：单项仍用 BLOCKER level，最终机器 verdict 改为 BLOCKED；summary 即使收到不一致 verdict，也会根据实际 blocker 列表 fail-closed，release_safe/deploy_allowed 不会假绿。
- model fallback summary 增加未知状态 fail-closed；PASS/DEBT/BLOCKER 三态明确。
- sandbox chunk warning 保持 DEBT 语义，并补齐嵌套 command_results[].chunk_warnings 与 stderr warning 的测试覆盖。

## 验证了什么
- ruff lint: dev_toolkit/release_gate.py、dev_toolkit/test_release_gate.py、dev_toolkit/module_sandbox_matrix.py、dev_toolkit/test_module_sandbox_matrix.py 全通过。
- pytest: test_release_gate.py 41 passed / 1 skipped；test_module_sandbox_matrix.py 19 passed；test_smoke_queue_gate.py 8 passed；test_release_response.py 5 passed；test_tool_job_tools.py 12 passed。
- module_sandbox_matrix(check=false): 35 pass / 0 fail / 0 skip。
- release_gate preflight skip-ui: PASS_WITH_DEBT，无 blockers，release_safe=true，deploy_allowed=true。
- release_gate full skip-ui job job_20260704142820_90ece148: PASS_WITH_DEBT，无 blockers，sandbox 35 pass / 0 fail / 0 skip，chunk warnings in 19；model fallback PASS；test-data pollution 0/0/0/0。

## 残留风险
- 当前工作区存在大量其他执行线的 dirty 文件，full gate 将 Git worktree 计为 DEBT；本信只提交 dev_toolkit 与项目记忆相关改动，不回退/混提其他 agent 改动。
- skip-ui 本身仍是 release debt，clean_release_ready=false。
