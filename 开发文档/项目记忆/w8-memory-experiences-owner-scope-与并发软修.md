---
name: "W8 memory_experiences owner scope 与并发软修"
type: "task"
tags: [memory, experience, owner-scope, concurrency, w8]
agent: "codex-w8"
created: "2026-07-02T11:58:43.751864+00:00"
---

# 改了什么
- 为 `memory_experiences` 增加兼容式 `owner_id` / `scope`：历史空 scope 迁到 `global`，新默认 `user`。
- `save_experience` 默认写当前用户 scope；普通 user caller 显式 `scope=global` 会被拒绝，系统 caller 可 curated global/team/user。
- `match_experience` 按可见范围过滤并按 user -> team -> global 优先级排序。
- `experience_feedback` 改成带 owner/scope 可见性校验的原子 `UPDATE ... RETURNING`，成功/失败计数不再读改写竞态。
- dream 只整理当前 scope；memory link 创建加唯一索引和 `ON CONFLICT DO NOTHING`，experience exact duplicate 加原子更新和唯一表达式索引兜底。

# 验证了什么
- ruff touched files 全通过；py_compile 全通过。
- `backend/tests/test_memory_experience_scope.py` 6 passed。
- `backend/tests/test_memory_core_paths.py` 38 passed；finish_task 合跑 44 passed。
- `modules/memory/sandbox/test_module.py` PASS。
- `run_init()` 成功，`memory_experiences` 真实表已有 `owner_id` / `scope`。
- `/api/health` 200 ok；当前源码进程验证 viewer 写 global 被 `PermissionDenied` 拦截。

# 残留风险
- 共享常驻后端未重启，live `/api/modules/call` 可能仍跑旧代码；曾用旧进程打了一条负向 live 调用并插入测试经验，已按 trigger 删除清理。
- 工作区有大量其他 agent/main-session dirty 文件，边界守卫因此报 outside_allowed；本轮实际改动限于 memory 后端、memory sandbox 和一个 memory backend 测试。
