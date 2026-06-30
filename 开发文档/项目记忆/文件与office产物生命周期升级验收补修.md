---
name: "文件与Office产物生命周期升级验收补修"
type: task
tags: ["artifact", "office", "excel-engine", "desktop-tools", "验收", "补修", "文件生命周期"]
created: 2026-06-30
agent: codex
---

验收 opencode 的“文件与 Office 产物生命周期一次性升级”。结论：原交付不是完全一条主线，存在三线并存：framework_artifacts 的 content_json/content_text/file-backed artifact、excel-engine 自己的 workbook/sheet/cell/history 表、office-gen 仍保留直接生成 file 的老能力。发现并修复真问题：1) excel-engine update_range/append_rows 在空工作簿时用 empty_state 覆盖 read_state_full 返回的 _sheet_id/_workbook_id，导致接口 success 但 excel_cells=0、导出空表；已移除覆盖并确保写入落库。2) undo/redo 只改内存 state 不 sync_cells，已改为撤销/重做后同步 cells/列宽/行高。3) excel-engine export_xlsx/publish_to_desktop 原本只生成 framework_file_items，未接 artifact；已改为导出/发布后创建 artifact，返回 artifact_id，并标记 source_module=excel-engine/source_object_type=workbook/source_object_id。4) artifact_service create_artifact(file_id=...) 仍重新 upload 导致同名冲突，已改为已有 file_id 只关联并创建版本；CREATE_VERSION 对已存在 artifact 会更新/版本化而非新建撞名。5) artifact restore_version 引用不存在的 Artifact.storage_path，已删除并正确恢复 file_id/storage_mode；replace_file_from_artifact 修复 content_json 二次编码并记录版本。6) Agent tool_guidance_service 原交付存在语法错误和 recipe_artifact_workflow 抢占 tool_not_found，已修复。验证：ruff 通过 artifact_service.py、excel-engine/router.py、excel-engine/state/db_ops.py、tool_guidance_service.py；后端重启 health ok module_errors=null；活系统 create_workbook→update_range→DB excel_cells=6→export_xlsx→parse file_id=588 内容正确→artifact_id 返回；publish_to_desktop 替换成功并可查版本；smoke_all skip_ui 26/26 绿；modules/agent/backend 161 passed。残留：excel-engine 无公开 delete_workbook/cleanup capability，验收留下 audit_tmp_excel_lifecycle 与 audit_fixed_excel_lifecycle 两个测试工作簿记录，未直接删库；长期架构仍需明确 canonical source：Excel 应以 excel_* 结构表为主，artifact 为发布/版本索引，不应同时把同一 Excel 正文又存 content_json。
