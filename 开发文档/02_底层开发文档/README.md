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

## Content IR 统一内容架构

Content IR (Intermediate Representation) 是统一结构化内容描述的框架层规范，所有结构化内容（文档、表格、演示、文本、图片等）经此链路流转：

```
Agent / Parser → Content IR → validate_ir → normalize_ir → write_ir → DB canonical source → viewer / compile
```

### 框架层文件

```text
backend/app/services/content/
  ir_schema.py      — Pydantic schema / 类型定义 + profile 规则
  ir_validator.py   — 两层校验：Schema 校验 + 语义 profile 校验
  ir_normalizer.py  — 补 block id、默认值、字段归一
  ir_writer.py      — 写入 ContentPackage / excel-engine / Resource / memory
  package_service.py — ContentPackage 的 CRUD、版本控制、资源管理
  resource_service.py — 内容寻址 Resource 存储（图片/VLM 元数据去重）
  export_service.py  — ContentPackage → 物理文件编译/导出/发布
```

### 注册的能力

| 能力 | min_role | 说明 |
|------|----------|------|
| `content:validate_ir` | viewer | 校验 IR 结构+语义，无副作用 |
| `content:normalize_ir` | viewer | 补 id/默认值/字段归一，无副作用 |
| `content:write_ir` | editor | 写入 DB canonical source（写前二次校验） |
| `content:compile` | viewer | 临时编译为下载文件，不创建 file record |
| `content:store_analysis_resource` | viewer | 解析器/VLM 回填 Resource（需 file_id 校验） |
| `content:store_resource` | editor | 编辑器以上角色存储二进制资源 |

### 校验与修正约定

- LLM 输出不可信，后端是所有 Content IR 规范的唯一裁判。
- validate_ir 校验失败返回结构化 errors（path/code/message/expected/actual）。
- write_ir 在写库前必须二次 validate，非法 IR 不写库。
- 自动修正循环最多 3 次，由 Agent `content_ir_correction.py` 驱动。
- 修正只处理结构，不改用户业务意图。

### 下载约定

- `GET /api/files/download/{file_id}` 优先 compile 内容 → 临时文件 → FileResponse + BackgroundTask 清理。
- ContentPackage 下载走 `content:compile`，Excel 下载走 `excel-engine:compile_xlsx`。
- 不创建 `framework_file_items` 记录。
- `download/original` 端点直接返回原件，跳过 compile。
- compile 返回路径受安全检查限制（仅允许 `.tmp_exports` / `.tmp_downloads` / 系统 temp）。

### Canonical Source 决策

- DB 是结构化内容的权威来源；物理文件只承担上传原件、显式发布产物、下载临时编译产物三类角色。
- Agent 和 parser 统一产出 Content IR，不再为 docx/xlsx/pptx/text 各维护一套 Agent 专属生成参数。
- viewer 默认读 DB canonical source；需要原件时走显式 `download/original` 或原件预览，不做静默降级。
- Excel 正文权威来源是 `excel_*` 结构表；普通文档、演示、文本、混合文档权威来源是 ContentPackage；图片/分析结果权威来源是 Resource。
- ContentPackage/Resource 继承文件权限：凡按 `file_id` 或 `source_file_id` 读取内容，必须先经 `check_file_access(db, file_id, user_id)` 校验 owner/share。
- Agent 不能直接创建或替换框架物理文件。结构化生成走 `content:*` / `excel-engine:*`；显式发布才创建 `framework_file_items`。
- `system:*` principal 只用于框架内受控流程；`write_ir` 不接受 owner_id=0 写入用户内容。

### Content IR Profile 口径

| content_type | 写入目标 | 关键限制 |
|--------------|----------|----------|
| `document` | ContentPackage | heading/paragraph/list/table/image/code 等文档块 |
| `presentation` | ContentPackage | 顶层 slide 为主，slide 内含标题、段落、图片、表格等 |
| `spreadsheet` | excel-engine | 顶层 sheet，sheet 下允许 table/range/cell_patch；`start_cell` 必须是合法 Excel 地址 |
| `text` | ContentPackage | paragraph/code/quote/heading 等文本块 |
| `image` | Resource | 图片、OCR、VLM 元数据和资源引用 |
| `mixed` | ContentPackage + Resource | 文档主体入 ContentPackage，二进制资源入 Resource |
| `memory` | memory capability | 只写结构化事实，不混入展示样式 |

## 健康检查与任务队列口径

健康信号必须服务于“发现真实不稳定”，不能只证明 HTTP 200。

- `/api/health` 是后端健康总入口；数据库、module_errors、worker、event_bus、任务队列语义失败都必须纳入降级判断。
- `/api/system/status`、前端状态面板、smoke 工具不得另造 worker 判断口径；worker 状态以 `task_worker.worker_health()` 为准，不能扫描旧的 `background_worker` 进程名。
- `smoke_all` 只算同步 happy path 不够。涉及上传、知识库、Agent 后台 hook、事件总线的场景，验收必须对比任务队列前后水位，确认本次测试没有新增失败。
- `framework_system_task_queues.failed` 不允许靠清表伪装健康；必须按错误类型分类：可归档历史噪音、需重试任务、需修复任务、需告警任务。
- 任务 handler 返回 `{error: ...}` 或内部 `success=false` 必须被 worker 识别为失败，禁止把语义失败记为 completed。
- 多 worker 共享状态必须落数据库或文件锁，不能依赖进程内内存。任务抢占必须使用数据库行锁或等价持久化 claim。

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

旧模块如果内部仍返回 `{"code": 1, "msg": "..."}`，必须在模块边界转换为统一失败语义；禁止把 legacy 失败包进外层 `{success:true,data:{code:1}}` 让调用方误判成功。

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
| Office | `framework_content_packages` `framework_content_package_versions` `framework_resources` `framework_resource_refs` `framework_artifacts` `framework_artifact_versions` `framework_artifact_operations` |
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
