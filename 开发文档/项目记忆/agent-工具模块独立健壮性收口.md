---
name: "Agent 工具模块独立健壮性收口"
type: "task"
tags: [agent-tools, terminal-tools, web-tools, browser-tools, desktop-tools, sandbox, capability-contract]
agent: "codex"
created: "2026-07-05T08:06:46.859561+00:00"
---

2026-07-05 Codex 完成业务模块执行信“agent 工具模块独立健壮性收口”。范围仅 modules/terminal-tools、modules/web-tools、modules/browser-tools、modules/desktop-tools。修复：browser-tools screenshot/download 结果从 host/workspace 绝对 file_path 改为 workspace_path 相对路径；browser README 补 URL/timeout/download/screenshot/failure/result shape；terminal sandbox 改为动态加载真实 backend/app/core/command_safety.py，README 修正 workspace 根、sandbox-exec fail-closed、public_actions 数量；web README 修正默认直连/WEB_TOOLS_PROXY 口径和 SSRF 负例。矩阵：terminal 8/8、web 2/2、browser 9/9、desktop 15/15，manifest/backend/README/sandbox 对齐。验证：ruff 四模块通过，frontend build 通过，四模块 sandbox 单跑 8/12/18/5 全过；合并 pytest 命令因四个 test_module.py 同名触发 pytest import mismatch，已记录；活系统 terminal list_workspace、desktop list_apps 成功，web/browser 内网 URL 返回 422 success:false。提交：479ad379 fix: harden agent tool modules。
