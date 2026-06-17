# 底层开发文档

## 底层目标

底层指 `backend/` 平台服务层，以及数据库、模型网关、队列、文件存储、权限、日志、配置、健康检查等基础能力。底层提供平台能力，不承载模块业务流程。

`backend/` 是平台服务层，不是业务后端大杂烩。业务模块可以调用底层能力，但业务本身应迁入 `modules/`。

## 当前真实状态

- 当前 `backend/` 是 Python FastAPI 后端，入口为 `backend/app/main.py`。
- 当前数据库初始化和释放在 `backend/app/database.py`，应用生命周期在 `backend/app/main.py`。
- 当前统一异常处理在 `backend/app/core/handlers.py`，自定义异常在 `backend/app/core/exceptions.py`。
- 当前 ORM model 在 `backend/app/models/`，schema 在 `backend/app/schemas/`，router 在 `backend/app/routers/`，service 在 `backend/app/services/`。
- 当前已注册认证、桌面、文件、回收站、用户、角色、系统、日志、仪表盘、设置、备份、任务、Office、通知、反馈、应用管理、AI 助手、图片视觉、知识库、菜单、健康检查等 router。
- 当前 AI 助手服务仍在 `backend/app/services/agent/`。
- 当前知识库服务仍在 `backend/app/services/knowledge/`。
- 当前模型看门狗在 `backend/app/services/model_watchdog/`。
- 当前默认 AI 助手模型为 `deepseek-v4-flash`，通过 `backend/app/services/agent/gateway/router.py` 路由。
- 当前模型配置由 `backend/app/config/models.json` 驱动。
- 当前旧 `/api/chat/*` 兼容入口已删除，AI 助手统一使用 `/api/agent/sessions/*`。
- 当前 `/api/health` 是唯一健康检查入口，`/api/health/deep` 已删除。

## 当前底层职责

- FastAPI 应用入口和路由注册。
- 数据库连接、事务、迁移、ORM 模型。
- 权限、角色、鉴权中间件。
- 队列、定时任务、worker。
- 模型看门狗、LLM 网关、embedding、rerank。
- 文件存储、上传下载、预览资源。
- 系统日志、健康检查、备份恢复。
- 统一 API 响应契约、异常处理、请求日志。

## API 契约

普通 JSON API 必须使用统一响应结构：

```json
{ "success": true, "data": {}, "error": null }
```

错误响应也必须使用统一结构，并通过 HTTP 状态码表达错误类型：

```json
{ "success": false, "data": null, "error": "Resource not found" }
```

实现规则：

1. 业务错误优先抛 `AppException` 子类，例如 `NotFound`、`ValidationError`、`ConflictError`、`PermissionDenied`。
2. 不要用 `return ApiResponse(success=False, ...)` 返回 HTTP 200 的业务失败。
3. `HTTPException` / `StarletteHTTPException` 由统一处理器兜底为 `{ success, data, error }`，但新增业务代码仍优先使用项目异常类。
4. 前后端字段名按后端实际返回的英文 `snake_case` 对齐，不通过 `转中文()` 改字段名。
5. `转中文()` 只允许作为 UI 展示层字符串映射工具，不参与 API 数据结构转换。

## 非 JSON 端点豁免

以下端点合法返回二进制、SSE 或 CSV，不套统一 JSON 外壳：

| 端点 | 类型 | 用途 |
|------|------|------|
| `GET /api/files/download/{file_id}` | `StreamingResponse` | 单文件下载 |
| `POST /api/files/download-multiple` | `StreamingResponse` | ZIP 下载 |
| `GET /api/knowledge/visual/page-image/{catalog_id}/{page_num}` | `FileResponse` | 知识库页图 |
| `GET /api/knowledge/visual/thumbnail/{catalog_id}/{page_num}` | `FileResponse` | 知识库缩略图 |
| `GET /api/knowledge/tasks/stream` | `text/event-stream` | 知识库任务进度 SSE |
| `POST /api/agent/sessions/{session_id}/stream` | `text/event-stream` | AI 助手流式回复 |
| `GET /api/roles/matrix/export` | `text/csv` | 角色矩阵导出 |

新增非 JSON 端点必须在这里登记，并在代码中明确返回类型。

## 类型和命名规则

- Python 代码使用英文命名、类型标注和 Router -> Schema -> Service -> Model 分层。
- 后端 JSON blob 字段优先使用 `TypedDict` 或具体类型，不用 `Any` 扩散类型边界。
- 当前 `backend/app/` 中仅保留 `backend/app/services/model_watchdog/router.py` 的 `**kwargs: Any`，用于兼容模型 provider 标准调用参数。
- 前端 API 类型必须与后端真实返回字段一致，后端返回 `entry_component_key`，前端也读取 `entry_component_key`。
- `frontend/src/` 仍存在一批历史中文变量名、函数名、类型名和 CSS 类名；新增或触达代码必须改为英文，历史代码随模块迁移继续分批清理。
- 除 `开发文档/` 外，目录名和文件名必须是英文。

## 脚本和部署

正式脚本使用英文目录：

```text
scripts/
backend/scripts/
frontend/scripts/
modules/{module}/sandbox/
deploy/
ops/
```

不再使用：

```text
脚本/
部署/
backend/脚本/
backend/_废弃/
```

## 测试和数据清理

- 测试可以创建数据，但必须清理。
- 上传样例、临时文件、测试日志、缓存结果不得长期保留。
- 数据库测试记录必须回滚或删除。
- 测试结果目录不作为事实源。
- 后端变更默认运行 `cd backend && .venv/bin/python -m pytest`。
- 前端变更默认运行 `cd frontend && npm run build`。
- 类型或契约清理后必须扫描 `as any`、`@ts-ignore`、`return ApiResponse(success=False, ...)` 和中文字段名残留。

## 当前验证基线

| 检查项 | 当前结果 |
|--------|----------|
| 后端测试 | `cd backend && .venv/bin/python -m pytest`：33 passed |
| 前端构建 | `cd frontend && npm run build`：通过 |
| 后端 `Any` | 仅剩模型看门狗标准 `**kwargs: Any` 和文档字符串提及 |
| `return ApiResponse(success=False, ...)` | 0 处 |
| `HTTPException` 业务路由直接抛出 | 0 处 |
| `.DS_Store` 残留 | 已清理 |
| `转中文()` 响应层调用 | 已移除 |
| `as any` / `@ts-ignore` 绕过 | 当前源码扫描为 0 处 |

## 当前架构债务

- 知识库、AI 助手、Office / 文件管理仍有大量业务 router、service、model、schema 位于 `backend/app/`，应按模块规范迁入 `modules/`。
- `modules/ai-assistant/` 已有前端模块和 sandbox 雏形，但后端、runtime、tests、test-data、assets、module-docs 和 sandbox pass/fail 门禁仍需补齐。
- `backend/app/main.py` 仍直接导入并注册大量业务 router，后续应改为模块清单扫描和动态挂载。
- 测试覆盖仍偏低，当前 33 个测试主要覆盖路由注册、网关 adapter 和少量桌面路由；后续应补统一响应契约、鉴权、关键业务 happy path 和非 JSON 豁免端点测试。
- 前端 `frontend/src/` 仍有历史中文标识符，后续按共享 API、desktop shell、window manager、context menu、module shell 分批英文化。
- `element-plus` 构建 chunk 仍较大，后续可结合按需导入或 vendor 分包处理。
