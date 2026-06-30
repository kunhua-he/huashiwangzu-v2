---
name: "文件与 Office 产物生命周期一次性升级"
type: task
tags: ["artifact", "lifecycle", "file-system", "desktop-tools", "office-gen", "excel-engine", "tool-guidance"]
created: 2026-06-30
agent: opencode
---

## 改了什么

### 1. 统一产物生命周期服务 (框架级)
- **新增** `backend/app/models/artifact.py` — Artifact / ArtifactVersion / ArtifactOperation 三表
- **新增** `backend/app/services/artifact_service.py` — 20+ 统一能力 (create/get/list/update/replace/delete/restore/rename/copy/move + version CRUD + export/publish + replace_file_from_artifact)
- **新增** `backend/app/routers/artifacts.py` — REST 端点 (注册在 PLATFORM_ROUTER_MODULES)
- **更新** `backend/app/models/__init__.py` — 导出新模型
- **更新** `backend/app/routers/registry.py` — 注册 artifacts router
- **更新** `backend/app/services/file_reader.py` — 新增 get_file_content_bytes() 工具函数

### 2. desktop-tools 完整 CRUD 升级
- **新增** 能力: get_file, create_file, delete_file, rename_file, copy_file, list_versions, restore_version, replace_file_from_artifact, publish_artifact
- **升级** replace_file: 支持 source_artifact_id / source_file_id / new_content 三种输入，移除 base64 依赖
- **更新** `manifest.json` — 同步 public_actions

### 3. office-gen 制品支持
- **新增** 能力: generate_to_artifact (无冲突生成), replace_existing (直接替换), export_to_artifact (导出为制品)
- **更新** `manifest.json` — 同步 public_actions

### 4. excel-engine 完整能力注册
- **新增** 12 个跨模块能力: create_workbook, import_file_to_workbook, update_range, append_rows, undo, redo, list_history, list_versions, restore_version, export_xlsx, publish_to_desktop
- **更新** `manifest.json` — 同步 public_actions

### 5. Agent 工具指引升级
- **更新** `tool_guidance_service.py` — 新增 Office 文件、Excel 编辑、桌面文件、Artifact 四条 default 指引 + artifact degradation recipe

## 解决的问题
- 同名文件冲突不再报死（支持 create_version/overwrite/auto_rename/replace_existing）
- Office 文件不再需要 Agent 手动 base64
- Excel 可通过数据库工作簿持续编辑并支持 undo/redo/version
- 二进制资源替换走 artifact 通路
- 删除支持软删除和还原

## 业务场景覆盖
- 场景1: 更新桌面已有 Excel ✓ (import_file_to_workbook → update_range → publish_to_desktop)
- 场景2: 生成新 Excel ✓ (create_workbook → update_range → export_xlsx/publish_to_desktop)
- 场景3: 替换已有 DOCX/PPTX ✓ (office-gen:generate_to_artifact → desktop-tools:replace_file_from_artifact)
- 场景4: 误操作回退 ✓ (excel-engine:list_history/undo/redo/restore_version)
- 场景5: 二进制资源替换 ✓ (create_artifact → replace_artifact_content → publish_artifact)

## 验证
- 后端健康: status=ok, module_errors=null
- 全回归 446 pytest: 全部通过
- smoke_all 26 场景: 全部绿色
- 活系统真打: artifact CRUD, excel-engine create_workbook/update_range/append_rows/undo/redo/export/list_history, office-gen generate_to_artifact 均返回 success=true

## 残留风险
- excel-engine publish_to_desktop 和 export_xlsx 使用临时文件后删除，理论上可能被其他服务残留
- artifact 的 content_json/content_text 目前只在 'db'/'draft' storage_mode 下存储，'file' 模式仅存 file_id
- 如需完全迁移现有文件到 artifact，需要额外迁移脚本
