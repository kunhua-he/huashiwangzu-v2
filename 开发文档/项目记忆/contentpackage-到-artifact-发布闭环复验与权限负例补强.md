---
name: "ContentPackage 到 Artifact 发布闭环复验与权限负例补强"
type: "task"
tags: [content-package, artifact, publish, verification, permission]
agent: "codex-content-artifact-publish-r1"
created: "2026-07-04T12:36:58.532968+00:00"
---

# 做了什么

读取并执行 `开发文档/项目记忆/执行信-ContentPackage到Artifact发布闭环.md`。当前分支主体闭环已存在：`content:write_ir -> content:publish` 可把 ContentPackage 发布为 `framework_artifacts + framework_file_items`，并回写 package publish 状态。

本轮主会话补强了一个自动化负例：`test_content_publish_non_owner_does_not_create_artifact_or_file`，确认非 package owner 调 `content:publish` 返回失败，且不会新增 artifact/file。

# 验证了什么

- `backend/.venv/bin/ruff check backend/app/routers/content.py backend/app/services/content backend/app/schemas/content_package.py backend/tests/test_content_artifact_publish.py` 通过。
- `test_content_artifact_publish.py` 单跑 8 passed。
- `test_content_ir_architecture.py` 单跑 55 passed。
- finish_task 合跑两组测试 63 passed。
- 活栈验证：`content:write_ir` 生成 `package_id=890/version_id=798`，`content:publish` 生成 `artifact_id=223/file_id=1051/published_version_id=378`；REST 包详情、文件详情和下载内容均验证通过。
- 探针数据已清理，artifact/file/package 计数回到基线。

# 残留风险

REST OpenAPI 尚未显式绑定 `PublishResponse` response_model。调用侧仍需区分：`content:compile` 是临时预览，`content:publish` 才是 artifact/file 持久发布。

# 关联 commit

未提交。
