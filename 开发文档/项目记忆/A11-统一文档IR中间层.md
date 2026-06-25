# A11-统一文档IR中间层（2026-06-25）
- Agent: A11-统一文档IR中间层
- 做了什么：将V2的半统一文档链路收口为平台级DocumentIR中间层
- 改了哪些：backend/app/schemas/document_ir.py(新增) + 3个parser + docs-open/content + json_package_service + office_export + office路由 + 3个出口服务
- 踩过的坑：package路由参数在query而非body（Internal Server Error误报）；md格式未在supported列表
- 遗留问题：无
