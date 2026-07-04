---
name: "桌面启动器过滤与 openWindow 反馈收口"
type: "task"
tags: [desktop, launcher, app-registry, window-manager, open-feedback]
agent: "codex-desktop-launcher-open-feedback-r1"
created: "2026-07-04T10:21:42.859227+00:00"
---

# 改了什么
- 在 `frontend/src/desktop/app-registry/app-visibility.ts` 统一直接可打开 app、后台能力和 openWindow 失败提示口径。
- 启动器普通列表通过 `isLauncherVisibleApp` 过滤，只保留 `showInLauncher` 且可直接打开的 app。
- 命令注册为搜索结果补充 `background-capability` 类型；后台/不可直接打开 app 及其 action 搜索结果标注“后台能力/不可直接打开”，执行时 toast `该能力是后台服务，不能直接打开窗口`。
- `shell/index.vue`、`desktop-app-handle-v2.ts`、`use-desktop-root-files.ts` 的 openWindow null 调用侧补用户可见提示。

# 验证了什么
- `cd frontend && npm run build` 通过。
- `rg -n "\\bany\\b|as any|@ts-ignore|@ts-expect-error" frontend/src/desktop/launcher frontend/src/desktop/app-registry frontend/src/desktop/window-manager frontend/src/desktop/shell` 无命中。
- `git diff --check -- frontend/src/desktop/launcher frontend/src/desktop/app-registry frontend/src/desktop/window-manager frontend/src/desktop/shell` 通过。

# 残留风险
- 当前工作区存在多个并行 worker 改动，包含 LoadState、fileops、shared/api、backend/dev_toolkit、agent 等；本轮未回退这些改动。
- `shell/index.vue` 与 `use-desktop-root-files.ts` 同时有其他 worker 的 LoadState 相关改动，本轮只追加 openWindow null 提示逻辑。

# 关联 commit
- 未提交。
