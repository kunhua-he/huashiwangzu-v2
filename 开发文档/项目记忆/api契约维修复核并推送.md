---
name: "API契约维修复核并推送"
type: task
tags: ["api-contract", "validation-error", "github", "commit-32127d44"]
created: 2026-06-30
agent: codex
---

复核 opencode 修复 4 处 ApiResponse(success=False) 返回 200 的 API 契约问题，确认 diff 仅两个目标代码文件加相关记忆文档。验证：rg 扫描 modules/browser-tools modules/agent 无剩余 success=False 响应；ruff lint 两文件通过；probe 四个端点均返回 422 + success:false。已提交并推送到 GitHub 当前分支，commit 32127d44 fix(api): raise validation errors for invalid module requests。
