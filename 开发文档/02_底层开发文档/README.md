# 底层开发文档

底层指 `backend/` 平台服务层，以及数据库、模型网关、队列、文件存储、权限、日志、配置、健康检查等基础能力。业务流程属于 `modules/`。

## Responsibilities

- FastAPI 应用入口和 router 注册。
- PostgreSQL 连接、事务和迁移。
- JWT 鉴权、角色和权限。
- 文件上传、下载、预览、分享、回收站和审计日志。
- 任务队列、worker、定时任务和模块 task handler。
- LLM gateway、embedding、rerank、vision 描述。
- Content IR、ContentPackage、Resource、Artifact。
- 统一 API envelope 和异常处理。

## Content IR

```text
Agent / Parser -> Content IR -> validate_ir -> normalize_ir -> write_ir -> DB canonical source -> viewer / compile / publish
```

Framework files:

```text
backend/app/services/content/ir_schema.py
backend/app/services/content/ir_validator.py
backend/app/services/content/ir_normalizer.py
backend/app/services/content/ir_writer.py
backend/app/services/content/package_service.py
backend/app/services/content/resource_service.py
backend/app/services/content/export_service.py
```

Rules:

- LLM output is not trusted; validators are the authority.
- `write_ir` validates again before DB writes.
- DB is the canonical source for structured content.
- Downloads compile temporary files; explicit publish creates framework file records.
- `source_file_id` / `file_id` reads inherit framework file permissions.

## Health And Queue Semantics

- `/api/health` is the backend health entry.
- `/api/system/status` and release tools must use the same worker health semantics.
- Worker/task handlers must treat `{error: ...}` or `success=false` as failure, not completed.
- Worker 领取任务前必须确认本进程已注册对应 `task_type` handler；不会处理的任务保持 `pending`，不能抢占后制造失败。
- 受控队列先按 `lane_key` 计算资源池预算，再领取任务；本地、VLM、LLM、派生索引、关系构建互不挤占，`stage_dispatch_order` 只在同资源池内决定先后。
- Pause is a queue contract: paused task/stage/lane must not be newly claimed; active cancellable tasks are cancelled and released back to `pending` with `blocked_reason=paused_by_config`.
- Long-lived worker processes may retire after memory pressure. Retirement stops new claims, releases active tasks through shutdown recovery, and lets the watchdog start a fresh process.
- Standalone task workers are scaled by the watchdog from executable queue pressure. Paused pending tasks do not keep workers resident; with `worker_min_processes=0`, an idle queue can drop to zero worker processes and wake workers when eligible tasks appear.
- Release validation must distinguish historical debt from new active failures.
- Multi-worker shared state must be persisted in DB or atomically written files.

## API Contract

Success:

```json
{ "success": true, "data": {}, "error": null }
```

Failure:

```json
{ "success": false, "data": null, "error": "Resource not found" }
```

Business errors raise framework exceptions (`NotFound`, `ValidationError`, `ConflictError`, `PermissionDenied`). Do not return fake-success HTTP 200 envelopes.

Non-JSON endpoints must be intentional, such as file downloads and CSV exports.

## Database Naming

Framework tables use `framework_*`. Modules use their own prefix and must not add DB-level foreign keys to framework or other module tables.

Common framework domains:

```text
framework_user_accounts
framework_role_matrices
framework_app_registry
framework_desktop_states
framework_file_*
framework_content_*
framework_resource_*
framework_artifact_*
framework_system_*
```

Use `db_schema()` for current table details.

## File Lifecycle

- Delete/recycle/restore/permanent-delete must keep Knowledge and ContentPackage lifecycle consistent.
- Test files must clean derived Knowledge documents and ContentPackages.
- Missing current artifact/content versions are release blockers.

## Verification

```bash
cd backend && .venv/bin/python -m pytest
python3.14 dev_toolkit/release_gate.py --preflight --skip-ui
```

Use `probe`, `call_capability`, and `tail_log` for live validation.
