---
name: "db-reverse-next-r5节点1-补齐框架分片上传会话链路"
type: "task"
tags: [db-reverse, file-upload-sessions, framework, chunked-upload, 20260703]
agent: "db-reverse-next-r5"
created: "2026-07-02T17:33:18.157101+00:00"
---

从 db_reverse_audit 反推发现 `framework_file_upload_sessions` 为空且只有模型引用：`FileUploadSession` 没有路由、服务、测试，属于真实半截底座。已补齐框架级分片上传小闭环：`POST /api/files/upload-sessions` 创建会话，`POST /api/files/upload-sessions/{session_id}/chunks` 接收 chunk，`POST /api/files/upload-sessions/{session_id}/complete` 合并并调用现有 `upload_file_from_path`，复用文件去重、目录权限、relative_path 与 file.uploaded 事件。同步将 `FileUploadSession` 导入 `app.models.__init__`，避免模型注册不稳定。验证：`backend/tests/test_file_upload_sessions.py` 2 passed；文件系统上传/去重/冲突/边界合约合跑 19 passed；focused ruff passed；`/api/health` 200。
