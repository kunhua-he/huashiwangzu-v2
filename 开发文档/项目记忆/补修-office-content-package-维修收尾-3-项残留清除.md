---
name: "补修：Office/Content Package 维修收尾 3 项残留清除"
type: task
tags: ["补修", "收尾", "office", "JSON Package", "terminal-tools", "测试"]
created: 2026-06-30
agent: opencode
---

## 补修内容

基于二次验收未通过的 3 项残留，逐一清理：

### 1. 删除旧 JSON Package ORM 文件
- `backend/app/models/office.py` 删除（内含 FileJsonPackage/FileJsonVersion/FileJsonPatch/FileJsonTask 四个旧模型）
- 该文件此前已无任何 import（`models/__init__.py` 和 `migrations/env.py` 已在上轮移除引用）
- 四张旧表（`framework_file_json_*`）仍保留在 DB，待独立迁移删除

### 2. terminal-tools runtime 残留方法清除
- `modules/terminal-tools/runtime/index.ts` 删除 `previewPatch()`, `applyPatch()`, `rollback()` 三个方法
- 上一个批量修复中因文本块不匹配遗漏了 terminal-tools（其他 27 模块已清理）

### 3. 测试文件重写
- `backend/tests/test_office_json_patch_flow.py` 重写：
  - 原 `test_office_patch_routes_require_auth` 改为 `test_office_patch_routes_deleted` 断言 404
  - 新增 `test_office_status_authenticated` 回归测试（断言不返回 500）
  - 新增 `test_office_status_nonexistent_file`（断言 404）
  - 保留 `test_office_package_versions_for_nonexistent`

### 验收
- `rg` 搜索结果干净：仅测试文件中作为 404 断言的字符串出现
- `pytest tests/test_office_json_patch_flow.py` — 4 passed
- 未改动 Content Package 主链路
