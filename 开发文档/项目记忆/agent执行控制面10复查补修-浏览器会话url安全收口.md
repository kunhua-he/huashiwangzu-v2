---
name: "Agent执行控制面10复查补修-浏览器会话URL安全收口"
type: task
tags: ["agent", "Agent10", "tool_guidance", "browser-tools", "安全边界", "降级", "回归测试"]
created: 2026-06-30
agent: codex
---

接手并复查 Agent执行控制面10（私有工具指引、失败降级、隔离 browser-tools）。上一轮已修：工具指引默认种子、render 合并顺序、skill_describe 注入、HTTP browser error envelope、redirect/final URL block、manifest public_actions、init seed。继续按分层复查发现同类安全遗漏：browser-tools 既有会话的 read_text/list_links/type/screenshot/download 在当前页已跳到 localhost/private/file 等 blocked URL 后仍可继续读或产出。已统一在这些 handler 使用 _ensure_allowed_current_url(page) fail-closed，并在 test_tool_guidance.py 增加 blocked session 参数化回归。验证：ruff 通过 browser.py 与 test_tool_guidance.py；pytest modules/agent/backend 161 passed；capabilities 显示 agent 工具指引能力和 browser-tools 9 能力注册；HTTP /api/browser-tools/open file:// 返回顶层 success:false；/api/modules/call browser-tools open 返回外层 success true、内层 success false，属现有跨模块包装形态未改框架。
