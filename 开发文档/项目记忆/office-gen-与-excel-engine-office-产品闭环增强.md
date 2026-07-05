---
name: "office-gen 与 excel-engine Office 产品闭环增强"
type: "task"
tags: [office-gen, excel-engine, sandbox, product-closure, artifact, export, publish]
agent: "codex"
created: "2026-07-05T08:12:53.851008+00:00"
---

Codex 执行“业务模块-执行信-office-gen与excel-engine独立产品化闭环”。改动限定在 modules/office-gen、modules/excel-engine 和项目记忆：office-gen 前端补文件/Artifact 双生成路径与 ContentPackage 状态展示，sandbox 增加 generate_to_artifact response shape；excel-engine 前端补保存/撤销/恢复/导出/发布成功反馈和模块能力调用，sandbox 增加 export_xlsx/publish_to_desktop shape，README 补产品闭环矩阵；同时手动清理 excel-engine 模块内既有 ruff 静态卫生债以满足模块级 lint。验证：ruff check modules/office-gen modules/excel-engine 通过；office-gen sandbox 9 passed；excel-engine sandbox 15 passed；合跑 --import-mode=importlib 24 passed；npm --prefix frontend run build 通过；活系统 office-gen:xlsx 生成 file_id=2084 后 excel-engine:parse 成功，office-gen:generate_to_artifact 返回 artifact_id=360/content_package_status=parsed，测试文件 2084/2088 已永久删除，artifact 360 软删除后 404。关联提交：本次任务提交。
