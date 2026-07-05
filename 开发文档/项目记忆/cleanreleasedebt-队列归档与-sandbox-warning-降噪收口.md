---
name: "CleanReleaseDebt 队列归档与 Sandbox warning 降噪收口"
type: "task"
tags: [release-gate, task-queue, sandbox-matrix, clean-release]
agent: "codex"
created: "2026-07-05T08:12:24.176931+00:00"
---

- 队列 deleted-source obsolete 债已归档：初始 6 条（6819, 6858, 6885, 6891, 6893, 6906）processed=6；后续 gate 期间新增的 8012、8006、8024 也已按 task_ids 归档；当前 live audit failed=0。
- 非 dry-run governance 增加显式安全守卫：必须传 task_ids 或 confirm_all_failed=true。
- Sandbox warning 降噪：Vite chunk-size warning 保留在 matrix/context 中，但 release gate 分类为 INFO，不计 clean debt；真实 fail 仍 BLOCKER。
- 修复 image-vision sandbox：schema_version 断言同步到 Content IR 当前标准 content-ir/v1。
- 修复 release gate 队列 clean 语义：deleted-source obsolete failed rows 不再计 active_failed，不触发 gate-run failed delta blocker。
- 最新 full release gate exit=0，blockers=[]，release_safe=true，deploy_allowed=true；clean_release_ready=false 的唯一原因是当前工作区存在非本信范围 dirty 文件。

队列最终：pending=0, running=0, completed=606, failed=0；historical_failed_debt_count=0；deleted_source_obsolete_failed_count=0。
Sandbox：35 modules / 35 pass / 0 fail / 0 skip；chunk_warning_count=19，模块为 agent、desktop-tools、doc-viewer、docx-parser、douyin-delivery、excel-engine、hello-world、image-viewer、image-vision、knowledge、pdf-parser、pdf-viewer、ppt-viewer、pptx-parser、terminal-tools、text-editor、text-parser、wechat-writer、xlsx-parser。
Full gate：UI passed=47 failed=0 skipped=0；Smoke clean pass；Model fallback PASS；Test pollution active=0/recycled=0/knowledge=0/content=0；Knowledge lifecycle source_unavailable=0。

提交：0078b4ad、ed8d227c。当前唯一剩余项为外部 dirty 工作区。
