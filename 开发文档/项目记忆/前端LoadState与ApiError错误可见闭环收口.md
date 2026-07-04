# 前端 LoadState 与 ApiError 错误可见闭环收口

执行 agent：`codex-frontend-loadstate-r1`

## 做了什么

- 统一前端 API 错误结构：`ApiErrorInfo` 保留 `httpStatus/http_status`、`code`、`backendMessage`、`userMessage`、`raw`，并提供 `toApiErrorInfo()` / `displayApiError()`。
- 新增通用 `LoadState<T>`：`idle/loading/ready/error/stale`，loading 不清空旧数据，刷新失败会保留上次成功数据并进入 `stale`。
- 新增 `LoadStateBanner`，用于错误/旧数据提示和重试按钮。
- 桌面根文件加载失败不再清空桌面文件图标；初次失败显示错误和重试，刷新失败保留旧图标并提示“桌面文件可能不是最新”。
- 文件管理器 `fm-state` 加入 LoadState；文件列表刷新失败不再伪装成“这个文件夹是空的”，已有数据时保留旧列表并显示 stale 提示。
- 通知/反馈中心各数据源独立记录加载状态；通知、任务、Agent、知识库任一 API 失败时不再显示“一切正常/没有需要处理的反馈”，而是显示失败来源和重试。

## 边界说明

执行信允许范围里点名了 `frontend/src/shared/files/fm-state.ts 或相关文件管理状态`，当前实际文件位于：

```text
frontend/src/platform/components/apps/desktop/file-manager/fm-state.ts
```

因此本次为完成点名验收，最小触碰了文件管理器实际路径及其两个 `FmFileList` 调用点。未修改后端、dev_toolkit 或模块后端。

## 验证

```bash
cd frontend && npm run build
```

结果：通过。

目标范围扫描：

```bash
rg -n "\bany\b|as\s+any|@ts-ignore|@ts-expect-error" \
  frontend/src/shared/api \
  frontend/src/shared/composables \
  frontend/src/shared/components \
  frontend/src/desktop/shell \
  frontend/src/desktop/taskbar \
  frontend/src/shared/files \
  frontend/tests \
  frontend/src/platform/components/apps/desktop/file-manager \
  frontend/src/platform/components/apps/desktop/index.vue \
  frontend/src/platform/components/apps/recycle/index.vue
```

结果：0 命中。

## 手工验收路径

1. 模拟 `/api/files/list` 失败：初次失败应显示桌面/文件管理器错误和“重试”；已有文件后刷新失败应保留旧文件并显示 stale 提示。
2. 模拟反馈中心任一接口失败：通知面板顶部应显示对应来源加载失败和重试，不显示“现在没有需要处理的反馈”。
3. 恢复接口后点“重试”：错误提示消失，列表/反馈恢复正常 happy path。
