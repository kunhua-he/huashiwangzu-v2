# 底层开发文档

## 底层目标

底层指 `backend/` 平台服务层，以及数据库、模型网关、队列、文件存储、权限、日志、配置、健康检查等基础能力。底层提供平台能力，不承载模块业务流程。业务模块可以调用底层能力，但业务本身应迁入 `modules/`。

## 当前状态

| 项 | 状态 |
|----|------|
| 后端框架 | FastAPI，入口 `backend/app/main.py` |
| 平台 router | 25 个（auth/desktop/files/file_shares/recycle/users/roles/system/logs/dashboard/settings/backup/tasks/notifications/feedback/office/editors/app_manager/menu/gateway/modules 等） |
| 模块事件总线 | `backend/app/services/module_events.py`：`register_module_event_handler(event, handler, module_key)` + `emit_module_event(event, payload, caller)`。框架不硬编码业务模块——如上传成功发 `file.uploaded`，knowledge 订阅入库（替代原硬编码 call knowledge:ingest）。单 handler 失败不阻塞其他 |
| 成本治理 | 网关每次调用按 token×单价记 `agent_usage_daily`（逐 agent 日用量）|
| 数据库 | PostgreSQL + SQLAlchemy async + Alembic，25 张 `framework_*` 表 + pgvector 扩展 |
| 模型网关 | `backend/app/gateway/`，DeepSeek/OpenCode/OpenAI 兼容协议，含降级链（primary → backup → cheap → echo）和视觉描述（MiMo VLM）。配置：模型档案/provider 在 `backend/data/config/models.json`；API key 在 `backend/.env`（opencode go 用 `DEEPSEEK_API_KEY`）|
| 模型看门狗 | `backend/app/services/model_watchdog/` |
| 模块代码 | 平台层已清空（AI 助手/知识库服务及 router 已删除） |
| pytest | 以 `cd backend && .venv/bin/python -m pytest` 当前结果为准 |
| 异常处理 | 统一 `{success, data, error}` + HTTP 状态码 |

## 职责清单

- FastAPI 应用入口和路由注册（`registry.py` 集中管理 + manifest 驱动挂载）
- 数据库连接、事务、迁移（`framework_*` 命名规范，Alembic 干净基线）
- 权限、角色、鉴权中间件（JWT HS256，24h，`session_version`）
- 队列、定时任务、worker：框架任务 worker 已实现（`app/services/task_worker.py`，消费 `SystemTaskQueue`，`FOR UPDATE SKIP LOCKED` 抢占 + 重试 + 超时回收 + lifespan 启停；模块用 `register_task_handler(task_type, handler)` 注册处理器，内置 `_echo` 自检）
- 模型看门狗、LLM 网关、embedding、rerank
- 文件存储：上传（200MB 上限、分块读防 OOM）、下载（`FileResponse`）、内容去重（`md5_hash` + 内容寻址，相同内容共享一份物理文件、复制复用不另存；删除统计同 md5 未删除记录数，归零才删盘；`ref_count` 为冗余字段，不参与删除判断）、分享（`framework_file_shares`）、回收站、预览、批量操作、路径面包屑
- 系统日志（含 12 种文件操作审计日志）、健康检查、备份恢复
- 统一 API 响应契约、异常处理、请求日志

## API 契约

正常响应：

```json
{ "success": true, "data": {}, "error": null }
```

错误响应：

```json
{ "success": false, "data": null, "error": "Resource not found" }
```

**规则**：业务错误抛 `AppException` 子类（`NotFound`/`ValidationError`/`ConflictError`/`PermissionDenied`），禁止 `return ApiResponse(success=False)` 返回 200。`HTTPException` 由统一处理器兜底。

### 文件系统错误码

| 状态码 | 场景 |
|--------|------|
| 400 | 请求非法（文件夹移动到自己） |
| 403 | 权限不足（跨用户操作目标目录） |
| 404 | 文件/文件夹/分享记录不存在或不可访问 |
| 409 | 重名冲突 |
| 413 | 文件过大或预览超限 |
| 500 | 磁盘文件丢失、不可读 |

### 非 JSON 端点豁免

| 端点 | 类型 | 用途 |
|------|------|------|
| `GET /api/files/download/{file_id}` | `StreamingResponse` | 单文件下载 |
| `POST /api/files/download-multiple` | `StreamingResponse` | ZIP 下载 |
| `GET /api/roles/matrix/export` | `text/csv` | 角色矩阵导出 |

新增非 JSON 端点须在此登记。

## 数据库表命名

格式：`{owner}_{domain}_{sub_domain}`，小写英文+数字+下划线。框架使用 `framework_` 前缀，模块使用自身 key。

| 域 | 表 |
|----|-----|
| 用户与权限 | `framework_user_accounts` `framework_role_matrices` |
| 应用 | `framework_app_registry` `framework_desktop_states` |
| 文件 | `framework_file_folders` `framework_file_items` `framework_file_recycle_items` `framework_file_shares` |
| Office | `framework_content_packages` `framework_content_package_versions` `framework_artifacts` `framework_artifact_versions` `framework_artifact_operations` |
| 系统 | `framework_system_logs` `framework_system_notifications` `framework_system_notification_reads` `framework_system_feedbacks` `framework_system_tasks` `framework_system_settings` `framework_system_task_queues` |
| Prompt | `framework_prompt_categories` `framework_prompt_templates` |

## 测试与验证

```bash
cd backend && .venv/bin/python -m pytest
cd frontend && npm run build
```

关键扫描：

```bash
rg -n "ChatSession|ChatMessage" backend/app backend/migrations              # 0
rg -n "return ApiResponse(success=False" backend/app/routers               # 0
rg -n "\.md5[^_]" backend/app/services                                    # 仅 hashlib.md5()
rg -n "owner_id" backend/app/services/file_service.py                      # 全部过滤
rg -n "check_file_access" backend/app/routers/file_transfer.py             # download 有
```

测试数据用完必须清理。上传样例、临时文件、测试日志不长期保留。
