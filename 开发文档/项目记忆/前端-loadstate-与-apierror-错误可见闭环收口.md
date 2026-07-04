---
name: "前端 LoadState 与 ApiError 错误可见闭环收口"
type: "task"
tags: [frontend, loadstate, api-error, notification, file-manager, desktop-shell]
agent: "codex-frontend-loadstate-r1"
created: "2026-07-04T10:27:41.603654+00:00"
---

完成前端 LoadState 与 ApiError 错误可见闭环：统一 ApiErrorInfo/toApiErrorInfo/displayApiError，新增 LoadState<T> 和 LoadStateBanner；桌面根文件、文件管理器、回收站文件列表、通知反馈中心失败时不再清空旧数据或显示假空态，已有成功数据刷新失败进入 stale 并提供重试。验证：cd frontend && npm run build 通过；目标范围 any/as any/@ts-ignore/@ts-expect-error 扫描 0 命中。收口文档：开发文档/项目记忆/前端LoadState与ApiError错误可见闭环收口.md。
