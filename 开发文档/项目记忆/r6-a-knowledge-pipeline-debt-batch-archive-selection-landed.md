---
name: "R6-A knowledge pipeline debt batch archive selection landed"
type: "task"
tags: [r6, knowledge, pipeline-debt, lifecycle, archive, dry-run]
agent: "codex-r6-knowledge-batch-a"
created: "2026-07-03T16:12:20.275884+00:00"
---

# 改了什么
- 在 modules/knowledge 内为 pipeline debt guarded archive 增加稳定选择层：category/categories/category_limits/limit_each/order。
- 保持旧参数兼容：未传选择参数时仍按原分类全集处理；显式 task_ids 是精确模式，不受 limit_each/category limits 截断。
- apply/dry-run 共用同一选择口径，返回 selected/not_selected/selected_by_category/not_selected_by_category/selection，并保留原 changed/skipped shape。
- 新增 knowledge:apply_pipeline_debt capability，dry_run 默认 true；更新 classify_pipeline_debt capability 元数据。
- 只改 modules/knowledge 下文件；当前工作区有其他 worker 的 dev_toolkit/frontend/media-intelligence dirty，未触碰未回退。

# 验证了什么
- ruff passed: pipeline_debt_service.py, pipeline_debt_api.py, router.py, test_pipeline_debt_service.py。
- pytest modules/knowledge/backend/tests/test_pipeline_debt_service.py: 14 passed。
- pytest modules/knowledge/backend/tests: 61 passed, 1 warning (github-search on_event deprecation)。
- manifest JSON valid。
- 活系统 HTTP dry-run: POST /api/knowledge/governance/pipeline-debt/apply with dry_run=true, category_limits {doc_missing:19, source_file_missing:21, source_file_deleted:20}, order=newest returned selected=60, changed=60, skipped=0, changed_by_category same as selected_by_category。
- 活系统 capability dry-run: knowledge:apply_pipeline_debt returned selected_by_category {doc_missing:19, source_file_missing:21, source_file_deleted:20}。

# 残留风险
- 当前真实数据 doc_missing 只有 19，因此三类各 20 只能做到 59；推荐主会话下一批用 19/21/20 达到 60。
- 重启后健康接口 failed 从 890 到 891，日志显示启动期间已有 file.uploaded/content pipeline 对 file_id=3240 失败，非 pipeline-debt apply 导致。

# 关联 commit
- 未提交。
