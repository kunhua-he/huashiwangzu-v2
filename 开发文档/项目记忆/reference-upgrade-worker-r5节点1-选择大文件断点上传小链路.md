---
name: "reference-upgrade-worker-r5节点1-选择大文件断点上传小链路"
type: "decision"
tags: [reference-upgrade-worker-r5, upload-session, reference-upgrade, 20260703]
agent: "reference-upgrade-worker-r5"
created: "2026-07-02T17:29:48.411096+00:00"
---

本轮读取 r4 参考升级报告和 reference_sources 目录后，在 workflow 能力编排、private modules 生命周期、大文件断点上传、Content IR parser quality profile 中选择“大文件/断点上传补齐 FileUploadSession 链路”。理由：它正好对应 framework_file_upload_sessions 空表，从后往前倒推是已建表未接路由；一期能限定在后端文件主链，最终 complete 复用现有 file_upload_service.upload_file_from_path 和 file.uploaded 事件，不造第二套文件入库逻辑；相比 workflow/private modules 风险更低，也不触碰用户明确排除的队列债、资源诊断、devtool agent board。已用 CodeGraph/路由/db_schema 核实：当前只有 /api/files/upload，FileUploadSession 模型无人依赖，表结构存在但无入口。
