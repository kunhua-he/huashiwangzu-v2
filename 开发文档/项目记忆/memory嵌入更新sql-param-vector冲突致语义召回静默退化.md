---
name: "memory嵌入更新SQL :param::vector冲突致语义召回静默退化"
type: gotcha
tags: ["memory", "embedding", "sql", "pgvector", "gotcha", "log_errors"]
created: 2026-06-25
agent: claude
---

06验收时log_errors(backend)照出一个潜伏很久的bug(非06引入): memory embedding_service._update_embedding_sql 用 'UPDATE memory_records SET embedding = :embedding::vector' —— SQLAlchemy text()的:embedding绑定参数紧挨pgvector的::vector转换语法, 编译给asyncpg时留野冒号→每次PostgresSyntaxError(syntax error at or near ':')被try/except吞成WARNING。后果: 所有记忆embedding写入失败(55条with_embedding=0), 语义召回静默退化成关键词, 很久没人发现。修: 改 CAST(:embedding AS vector) 避开::与:param冲突。注意区分: 同模块其他 '{vec_literal}'::vector 是字符串字面量+cast(f-string插值非绑定参数)不冲突, 不用改。旧记忆embedding需另跑backfill补。教训: ① :param紧挨::cast在SQLAlchemy text()里会冲突, 用CAST(); ② 这bug是log_errors在跑别的批(06)时顺带照出的——日志扫描型工具能跨任务发现潜伏问题, 印证'每批log_errors双扫'的价值。关联 [[运行时重构系统性盲区-多个引擎状态搬db漏owner-id-嵌套函数缺global]]。
