# 执行信：前端 LoadState 与 ApiError 错误可见闭环

## 一句话目标

把前端核心列表/反馈/文件视图从“接口失败就显示空态或正常态”，改成“失败可见、保留上次成功数据、可重试、错误原因能到用户”。

本任务只做前端错误可见性基础设施，不碰后端、不碰 release gate、不碰 Knowledge 后端、不碰 Agent 后端。

## 必读

```text
/Users/hekunhua/Documents/Agent/PHP/华世王镞_v2/AGENTS.md
/Users/hekunhua/Documents/Agent/PHP/华世王镞_v2/开发文档/README.md
/Users/hekunhua/Documents/Agent/PHP/华世王镞_v2/开发文档/01_框架开发文档/README.md
/Users/hekunhua/Documents/Agent/PHP/华世王镞_v2/开发文档/项目记忆/流程能力审计报告-20260704.md
```

## 修改边界

只允许修改：

```text
frontend/src/shared/api/
frontend/src/shared/composables/
frontend/src/shared/components/
frontend/src/desktop/shell/
frontend/src/desktop/taskbar/
frontend/src/shared/files/
frontend/tests/
开发文档/项目记忆/
```

禁止修改：

```text
backend/
dev_toolkit/
modules/knowledge/backend/
modules/agent/backend/
modules/*/backend/
```

如果必须新增类型/工具，请放在 `frontend/src/shared/` 下。

## 目标 1：统一 ApiError

建立或收口一个前端统一错误结构，至少保留：

```ts
interface ApiErrorInfo {
  httpStatus?: number
  code?: string
  backendMessage?: string
  userMessage: string
  raw?: unknown
}
```

要求：

1. 后端返回的 `error` / `message` / HTTP status 不要被全部泛化成“失败”。
2. 404 可以保留通用用户文案，但调试信息里必须保留 backend message。
3. 提供统一 helper，例如：

```ts
toApiErrorInfo(error, fallbackMessage)
displayApiError(error, fallbackMessage)
```

4. 禁止使用 `any`、`as any`、`@ts-ignore`、`@ts-expect-error`。

## 目标 2：统一 LoadState

新增或收口通用状态模型：

```ts
type LoadStatus = 'idle' | 'loading' | 'ready' | 'error' | 'stale'

interface LoadState<T> {
  status: LoadStatus
  data: T
  error: ApiErrorInfo | null
  lastLoadedAt?: string
}
```

要求：

1. 初次加载失败：显示 error，不显示“空列表/没有问题”。
2. 已有数据后刷新失败：保留旧数据，状态为 `stale`，显示“数据可能不是最新 + 重试”。
3. loading 时不要清空旧数据。
4. 提供通用错误/重试 UI 小组件或 composable，避免各处重复写。

## 目标 3：改造核心风险点

至少覆盖这些审计里点名的地方：

```text
frontend/src/desktop/shell/use-desktop-root-files.ts
frontend/src/shared/files/fm-state.ts 或相关文件管理状态
frontend/src/shared/composables/use-notifications.ts
frontend/src/shared/components/notification-panel.vue
```

要求：

1. catch 中不得无提示置空核心数据。
2. 通知/反馈中心 API 失败时，不得显示“现在没有需要处理的反馈”。
3. 文件/桌面列表失败时，要显示错误和重试，已有数据则保留为 stale。
4. 保持现有正常 happy path 行为。

## 目标 4：测试与扫描

必须做：

```bash
cd frontend && npm run build
```

并扫描目标范围内不得出现：

```text
any
as any
@ts-ignore
@ts-expect-error
```

如果仓库已有前端单测/Playwright 可轻量覆盖，则补最小测试；如果没有合适测试，至少写明手工验证路径。

## 验收标准

```text
frontend build 通过
目标文件无 any/as any/@ts-ignore/@ts-expect-error
API 失败不会被渲染成空态/正常态
已有数据刷新失败时保留 stale data
通知中心失败时显示错误/重试，不显示“没有问题”
```

## 交付

写入项目记忆：

```text
开发文档/项目记忆/前端LoadState与ApiError错误可见闭环收口.md
```

并调用：

```text
finish_task(...)
memory_write(agent="codex-frontend-loadstate-r1")
mcp_feedback(agent="codex-frontend-loadstate-r1")
```

## 提示词

请读取并执行：‘/Users/hekunhua/Documents/Agent/PHP/华世王镞_v2/开发文档/项目记忆/执行信-前端LoadState与ApiError错误可见闭环.md’
