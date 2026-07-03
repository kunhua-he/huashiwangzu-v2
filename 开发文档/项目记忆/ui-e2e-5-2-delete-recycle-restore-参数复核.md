---
name: "UI e2e 5.2 delete recycle restore 参数复核"
type: "task"
tags: [ui-e2e, recycle, restore, convergence]
agent: "codex-convergence-ui-worker"
created: "2026-07-03T17:12:43.124476+00:00"
---

子代理 B 复核 frontend/tests/ui-e2e.spec.mjs 的 5.2 File delete+recycle 场景。通过 routes/code_explore/code_node 确认 /api/recycle/restore 使用 RestoreRequest(item_type, id)，后端 recycle_service.restore_item 以 db.get(RecycleItem, id) 查询，因此 id 是 framework_file_recycle_items 的回收站条目 id，原文件 id 在 origin_id。最小修改：回收站匹配使用 origin_id/name，waitForDeletedAndRecycled 返回匹配的 recycleItem，restore 改传 { id: recycleItem.id, item_type: recycleItem.item_type || 'file' }，并保留 expect.poll 条件等待。验证：node --check frontend/tests/ui-e2e.spec.mjs 通过；probe /api/recycle/list 200 且返回 id/origin_id/item_type；npx playwright test tests/ui-e2e.spec.mjs -g "5.2 File management - delete and recycle" --workers=1 通过 1/1。未提交 commit。
