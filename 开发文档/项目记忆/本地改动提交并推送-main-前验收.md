---
name: "本地改动提交并推送 main 前验收"
type: "task"
tags: [git, main, push, dev-toolkit, testing]
agent: "codex-main-push"
created: "2026-07-03T19:06:58.955737+00:00"
---

# 改了什么
- 按用户要求以本地为主，准备将当前本地测试加速与 MCP 工具台升级改动提交并推送到 GitHub main。
- 本地 main 在 fetch 后仍与 origin/main 同步，未发现远端分叉。

# 验证了什么
- ruff: dev_toolkit/release_gate.py、module_sandbox_matrix.py、worktree_tools.py、tool_job_tools.py、timing_tools.py、core_tools.py、server.py 全绿。
- pytest: dev_toolkit/test_release_gate.py dev_toolkit/test_module_sandbox_matrix.py dev_toolkit/test_worktree_tools.py dev_toolkit/test_tool_job_tools.py dev_toolkit/test_timing_tools.py dev_toolkit/test_server_helpers.py -> 93 passed, 1 skipped。
- release gate preflight skip-ui: PASS_WITH_DEBT，release_safe=true，无 blocker。
- tool_job 后台通路自测：test_tool_job_tools.py 12 passed；lint tool_job_tools.py 全绿；test_timing_tools.py 4 passed。
- worktree_guard 边界检查通过，dirty 均在 backend/pytest.ini、pytest.ini、dev_toolkit/、开发文档/项目记忆/ 范围内。

# 是否还有残留风险
- preflight 使用 --skip-ui 与 --preflight，因此结果是 PASS_WITH_DEBT，不是完整 clean release gate。
- 本次按用户要求直接合入 main，未拆 PR。

# 关联 commit
- f2f1b18a chore: speed up dev toolkit checks
