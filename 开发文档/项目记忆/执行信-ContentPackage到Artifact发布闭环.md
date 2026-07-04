# 执行信：ContentPackage 到 Artifact 发布闭环

## 目标

把 ContentPackage 从“后台结构化包”推进到“用户可见/可下载/可追溯 Artifact”。用户说生成文件、放桌面、给我文档时，必须能形成 artifact/file 记录，而不是只停在 package。

## 修改边界

允许：

```text
backend/app/routers/content.py
backend/app/services/content/
backend/app/models/content.py
backend/app/models/asset.py
backend/app/schemas/content_package.py
backend/tests/test_content_ir_architecture.py
backend/tests/test_content_artifact_publish.py（可新建）
开发文档/项目记忆/
```

禁止：

```text
dev_toolkit/release_gate.py
backend/app/routers/modules.py
modules/agent/
modules/knowledge/
frontend/
```

## 必做

1. 定义状态机：

```text
draft_package -> compiled_preview -> published_artifact/file
```

2. `content:publish` 必须创建或更新用户可见 artifact/file，并返回：

```text
package_id
artifact_id
file_id 或 download_url
published_version_id
status
```

3. publish 必须校验权限，继承 `check_file_access` / owner 规则。
4. compile 临时文件仍可存在，但 publish 结果必须持久化到框架 artifact/file。
5. ContentPackage response 增加清晰 publish 状态。
6. 不直接改 Agent；只提供稳定能力给 Agent 后续调用。

## 验收

必跑：

```bash
backend/.venv/bin/ruff check backend/app/routers/content.py backend/app/services/content
backend/.venv/bin/python -m pytest backend/tests/test_content_ir_architecture.py
backend/.venv/bin/python -m pytest backend/tests/test_content_artifact_publish.py
```

活栈验证：

```text
content:write_ir -> content:publish -> 产生 artifact/file
/api/content/packages/{id}/publish 返回 artifact/file 信息
framework_artifacts 从 0 或原值增加
发布文件可下载/可在文件系统中查询
```

## 交付

写：

```text
开发文档/项目记忆/ContentPackage到Artifact发布闭环收口.md
```

调用：

```text
finish_task(...)
memory_write(agent="codex-content-artifact-publish-r1")
mcp_feedback(agent="codex-content-artifact-publish-r1")
```

## 提示词

请读取并执行：‘/Users/hekunhua/Documents/Agent/PHP/华世王镞_v2/开发文档/项目记忆/执行信-ContentPackage到Artifact发布闭环.md’
