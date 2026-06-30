---
name: "旧 framework_file_json_* 四表退役迁移与文档收口"
type: task
tags: ["migration", "drop-legacy-tables", "content-package", "framework"]
created: 2026-06-30
agent: opencode
---

# 改了什么
- 从真实开发库执行 `alembic upgrade head` 将退役迁移 132d955fc2d4 应用到数据库
- DROP 四张旧表：framework_file_json_packages/versions/patches/tasks（按 FK 依赖顺序）
- 框架/底层 README 的"现役表"清单从旧四表替换为 Content Package/Artifact 当前契约，表计数 21→25

# 验证了什么
- 前置门禁：四表逐项 SELECT count(*) 全部 0 行，alembic_version=3b8f6e1a2c4d
- 真实库：四表从 information_schema 消失，alembic current=132d955fc2d4
- 隔离临时库：创建→alembic upgrade head→验证无旧表→DROP，全链通过
- ORM metadata 无 file_json 表；旧 patch 端点 404，Office status 正常
- 8/8 测试通过（4 migration + 4 office regression）

# 残留风险
无

# 关联 commit
迁移文件和测试文件已存在于上一轮 commit，本次为实际迁移执行与文档更新。
