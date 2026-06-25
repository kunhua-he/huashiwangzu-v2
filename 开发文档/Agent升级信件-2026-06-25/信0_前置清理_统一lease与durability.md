# 任务信：信0 — 前置清理：统一 lease 与 durability（清地基）

> 这是整批信的第 1 封，地基中的地基。必须最先做完。
> 依据：审计 §3 可合并清单（行 79）+ §6 持久化隐患（行 157）+ §7 前置建议 P0/P1。
> 这一封做完，信1（A1）的 task_sink 和 信9（A9）的 health 模型才有统一底座。

---

## 任务目标

本信只解决一件事：把 V2 当前**两套各自正确但互不相认的后台可靠性机制**，合并成一套统一抽象。
外加 3 个 P0 级的 parser 清理（它们挡着 A1 和 A11）。

不要顺手做 A1 主循环重构，不要顺手做 A9 health 大盘。本信只清地基。

## 为什么现在做这个

审计点名（§1 + §3 + §7）：V2 底座有重复实现，不先清，A1/A9 会在脏地基上盖楼，且各自再发明一遍稳定性补丁。

具体两套重复：

1. **lease/leadership 双实现**
   - `backend/app/services/task_worker.py:57-79`（stale 回收）+ `:113-142`（`FOR UPDATE SKIP LOCKED` 抢任务）—— 标准 SQLAlchemy ORM 做法
   - `modules/agent/backend/engine/post_turn_hooks.py:504-537`（DB 行级 leadership claim）+ `:540-560`（heartbeat）—— **原始 SQL，PostgreSQL 方言，硬编码 `id=1`**（审计 §6 行 157：不可移植）
   - 两套解决同一类问题，字段、回收逻辑、超时口径都不统一

2. **parser 模板化拷贝（P0，挡着 A1/A11）**
   - 5 个 parser 各有逐字拷贝的 `_resolve_user_id()` + 文件路径安全校验（审计 §2.1 行 36-41）
   - 框架层 `office/docx_service.py`、`pptx_service.py`、`excel_service.py` 还保有一份和模块层 parser 做同一件事的实现（审计 §2.2 行 48-50）

## 当前事实（V2）

| 重复点 | 位置 A | 位置 B | 审计依据 |
|--------|--------|--------|----------|
| lease/heartbeat | `post_turn_hooks.py:504-560`（原始SQL，硬编码id=1） | `task_worker.py:57-142`（ORM） | §3 行79、§6 行157 |
| `_resolve_user_id` | 5 个 `modules/*-parser/backend/router.py:23-32` 逐字拷贝 | — | §2.1 行36-41 |
| 文件路径校验 | 5 个 parser 的 `_parse()` 开头 20 行 | — | §2.1 行41 |
| 业务 parser | `backend/app/services/office/{docx,pptx,excel}_service.py` | `modules/{docx,pptx,xlsx}-parser/` | §2.2 行48-50 |

## 本次要改什么

### 1. 抽统一 DurabilityHelper（审计 §3 行79，P1，~6h）
新建 `backend/app/services/durability.py`：
```
class DurabilityHelper:
    claim_lease(table, worker_id, stale_after) -> bool
    heartbeat(table, worker_id)
    stale_takeover(table, stale_after) -> bool
    release(table, worker_id)
```
- `task_worker` 和 `post_turn_hooks` 各自**改成调用它**，不再各写一套
- 统一用 ORM `with_for_update(skip_locked=True)`，**消除 post_turn_hooks 的原始 SQL 和硬编码 id=1**（审计 §6 行157）
- 顺手修审计 §6 行159 的隐患：heartbeat 改成独立超时检查，不再只在一轮 maintenance 成功后才写（消除 ~11 分钟空窗）

### 2. 抽框架级 read_uploaded_file（审计 §7 P0，~3h）
新建 `backend/app/services/file_reader.py`：
```
read_uploaded_file(db, file_id, user_id, allowed_exts) -> (File, Path)
```
- 内含 `check_file_access` + storage_path + upload_root + commonpath 安全检查
- 5 个 parser 改成调用它，删掉各自拷贝的 `_resolve_user_id` 和路径校验
- `_resolve_user_id` 抽到 `backend/app/core/user_utils.py` 共用

### 3. 删框架层业务 parser（审计 §7 P0，~0.5h）
- 删 `backend/app/services/office/docx_service.py` 的 `DocxService.parse()`
- 删 `pptx_service.py` 的 `PptxService.parse()`
- 删 `excel_service.py` 的 `ExcelService.parse()`
- 改任何引用方指向模块层 parser（先用 codegraph 查 callers，确认没有活引用再删）

## 本次不要改什么

- 不要统一 parser 的返回 schema（那是信11 Document IR 的活，本信只清重复函数）
- 不要做 A1 主循环重构
- 不要做 A9 health 大盘
- 不要碰 retry/fallback 四层（那是信5 的活）
- 不要改业务逻辑，只搬重复代码

## 验收

### 单测
- `backend/tests/test_multiworker_file_race.py`（lease 行为不退化）
- `backend/tests/test_module_boundary_contracts.py`
- 5 个 parser 各自的现有测试（路径校验不退化）
- 新增 `backend/tests/test_durability.py`：claim/heartbeat/stale_takeover/release

### 活系统
- 多 worker 下后台维护任务仍单主执行，不重复跑
- 5 个 parser 解析仍正常（用 call_capability 各打一次）
- 删框架 parser 后，调用方仍能解析（probe 验证）

### 行为口径（做完必须全部成立）
1. `post_turn_hooks` 和 `task_worker` 都改用 `DurabilityHelper`，**各自的私有 lease 实现已删除**
2. post_turn_hooks 不再有原始 SQL 和硬编码 id=1
3. heartbeat 空窗隐患消除
4. 5 个 parser 不再有拷贝的 `_resolve_user_id` 和路径校验
5. 框架层 3 个业务 parser service 已删，无残留引用

## 回信格式

按 `00_投递总说明.md` 第七节。
核心思想守门项：本信是**删重复**不是加抽象层——回信必须确认旧的两套 lease、5 份拷贝、3 个框架 parser 是**真的删掉了**（贴出 git diff 的删除行数），而不是新增了 DurabilityHelper 但旧代码还在并存。
第 5 节说明给信1（task_sink）和信9（health 模型）留的接口。
