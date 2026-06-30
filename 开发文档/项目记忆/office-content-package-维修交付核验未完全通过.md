---
name: "Office Content Package 维修交付核验未完全通过"
type: task
tags: ["audit", "office", "content-package", "opencode", "repair-followup"]
created: 2026-06-30
agent: codex
---

核验 opencode 的 Office/Content Package 孤儿代码维修交付。通过项：/api/office/status/1 已 200，/api/office/patch/preview 已 404，office 路由只剩 status/package/versions；/api/modules/capabilities 确认 content 能力存在；office-gen 当前调用 ContentPipelineService.run_pipeline_for_package；excel_versions 仍为 0 且已按限制能力处理。未通过项：backend/app/models/office.py 旧 FileJson* ORM 文件仍存在；modules/terminal-tools/runtime/index.ts 仍保留 previewPatch/applyPatch/rollback 调已删除端点；backend/tests/test_office_json_patch_flow.py 仍按旧端点 401 写断言，targeted pytest 1 failed/1 passed。结论：主链路已修，但不能进入下一封升级信，需短补修收尾。
