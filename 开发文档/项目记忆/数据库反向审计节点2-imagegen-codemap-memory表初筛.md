---
name: "数据库反向审计节点2-imagegen-codemap-memory表初筛"
type: "task"
tags: [db-backtrace, image-gen, codemap, memory, empty-table, audit]
agent: "db-backtrace-worker"
created: "2026-07-02T16:03:14.852682+00:00"
---

节点2：继续使用 dev_toolkit db_reverse_audit 只读审计。imagegen_records row_count=0，owner=image-gen，code_reference_count=6，分类 requires_flow_probe/code_without_data；codemap_feedback row_count=0，owner=codemap，code_reference_count=8，分类 requires_flow_probe/code_without_data；memory_links row_count=0，owner=memory，code_reference_count=14，工具分类 expected_empty。初步判断：image-gen/codemap 需要验证写入流程是否真实可达；memory 链接/经验表需要确认是否存在产品入口、是否只是治理/反馈未触发。当前未修改代码。
