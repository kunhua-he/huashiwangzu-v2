---
name: "维修 — 修复 4 处 ApiResponse(success=False) 返回 200 的 API 契约问题"
type: task
tags: ["维修", "API契约", "ValidationError", "422", "browser-tools", "agent"]
created: 2026-06-30
agent: opencode
---

# 维修记录

## 修复内容
将 4 处 `return ApiResponse(success=False, error=...)`（HTTP 200）改为 `raise ValidationError(...)`（HTTP 422），对齐项目 API 契约。

## 改动的文件
- `modules/browser-tools/backend/router.py` — `_browser_response` 函数中 error 分支: `return ApiResponse(success=False, ...)` → `raise ValidationError(...)`；新增 `from app.core.exceptions import ValidationError`
- `modules/agent/backend/router.py` — 3 处: rollback_conversation(缺message_id)、edit_resubmit(缺content)、rollback_tool_guide(缺version) 全部 `return ApiResponse(success=False)` → `raise ValidationError(...)`；新增 `from app.core.exceptions import ValidationError`

## 验证结果
1. **静态扫描** `grep -n "ApiResponse.*success=False" modules/browser-tools modules/agent` → CLEAN
2. **Lint** 两个文件均 `All checks passed!`
3. **活系统验证（probe）**
   - `POST /api/agent/conversations/99999/rollback` {} → 422 `{"success":false,"error":"message_id required"}`
   - `POST /api/agent/conversations/99999/messages/1/edit-resubmit` {"content":""} → 422 `{"success":false,"error":"content is required"}`
   - `POST /api/agent/tool-guides/99999/rollback` {} → 422 `{"success":false,"error":"version is required"}`
   - `POST /api/browser-tools/read-text` {"session_id":""} → 422 `{"success":false,"error":"no active session, call open first"}`
4. **边界检查** `git diff --name-only` → 仅 modules/agent/backend/router.py 和 modules/browser-tools/backend/router.py

## 残留风险
无。4 处问题全部修完，成功路径行为不变。
