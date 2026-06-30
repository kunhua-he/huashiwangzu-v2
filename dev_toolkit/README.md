# 项目工具台 MCP Server

开工先连我。`python3.14 dev_toolkit/server.py` (stdio), 注册在 `.mcp.json`。

通过 MCP 协议暴露项目开发加速工具, 供 AI agent 直接调用。

## 标准工作流（所有任务必须遵守）

### 工作流总览

```
brief (全景理解)
  → plan_task (生成计划 + 预采证据)
    → 按 required_evidence 逐一收集证据
      → 制定修改方案
        → quick_fix_preview / patch 执行修改
          → lint + run_test + probe + tail_log 验证
            → finish_task (汇总 + 边界检查 + 风险评估)
              → memory_write (留痕归因)
```

### 各阶段详解

#### 阶段 1：全景理解 → `brief()`
开工第一条。读项目全貌：README、最近变更、投递箱待处理、Git 工作区状态、最近项目记忆。

**如果已经调过 brief 并且工作区无变化，可跳过。**

#### 阶段 2：任务计划 → `plan_task(description, task_type, module_key)`
标准工作流入口。调此工具自动做三件事：
1. 预采部分证据（模块能力 / 表结构）
2. 生成结构化计划（问题理解、required_evidence 清单、modification_boundary、verification_plan、workflow 步骤）
3. 输出分步工作流，agent 须严格按步骤执行

**输出包含：**
- `problem_understanding` — 问题理解，禁止未理解就改代码
- `required_evidence` — 必须收集的证据清单（工具名 + 原因）
- `pre_gathered_evidence` — 已自动预采的证据（能力列表、表结构等）
- `modification_boundary` — 改动边界（允许目录、禁止操作）
- `verification_plan` — 验证计划（lint/test/probe/log）
- `rollback_and_risk` — 回滚方法与风险等级
- `workflow` — 分步工作流步骤

#### 阶段 3：证据收集
严格按照 `required_evidence` 清单逐一调用工具。代码修改类任务**必须**收集的证据：

| 工具 | 为什么必须调 |
|------|-------------|
| `code_explore(query)` | 探索代码：符号 / 调用链 / 影响面 |
| `code_node(symbol)` | 读取关键符号 / 文件定义 |
| `code_impact(path)` | 查看改动影响面（波及哪些文件/模块） |
| `routes(filter)` | 查准后端端点（确认 API 路径/参数/方法，不靠猜） |
| `capabilities(module)` | 查准模块能力和参数名 |
| `db_schema(table)` | 查准数据库表结构（列名/类型/nullable，不靠猜） |

**禁止直接凭猜测改文件。** 上述工具必须调过再动手。

#### 阶段 4：执行修改
基于证据确定具体改动，用 `quick_fix_preview` 预览 → `quick_fix_patch` 落盘。

**改动边界规则（由 modification_boundary 强制执行）：**
- 模块任务只允许改 `modules/{module_key}/` 内
- 禁止直接 import 其他模块代码
- 禁止直接读写其他模块的表（只能读写 `{module_key}_*` 表）
- 跨模块调用必须通过框架统一通路：runtime SDK 或 `/api/modules/call` + 能力注册表
- 框架能力和模块能力边界保持清晰：加模块不改框架

**模块开发任务禁止修改框架。** 所有改动只许落在 `modules/{模块}/` 内。需要框架新增公共能力时，必须作为独立「框架任务」单独提出。验收硬守卫：`git diff --name-only` 确认所有改动在模块目录内。

#### 阶段 5：验证
按 `verification_plan` 执行验证。规则：

| 场景 | 优先用 | 说明 |
|------|--------|------|
| 后端改动 | `run_test` | 默认跑相关测试，返回结构化结果 |
| 接口问题 | `probe(method, path, body)` | 自动登录后打后端任意接口，不写测试脚本 |
| 跨模块调用 | `call_capability(module, action, params)` | 调模块能力，不走直接 import |
| 日志排查 | `tail_log(module, lines)` | 先看日志尾部，确认无新增错误 |
| 端口/状态 | `sanity_check()` | 前端端口 + 后端健康 + 模块导入 + 知识图谱 |
| 静态检查 | `lint(path, diff)` | ruff 检查 Python 代码 |

**修改后必须有验证结果，不能停留在推测。**

#### 阶段 6：收尾留痕 → `finish_task` + `memory_write`

**`finish_task(summary, agent, lint_paths, test_targets, module_key, verification_summary, risk_note)`**

收尾检查，不是仅做摘要。输出包含：
- `git` — Git 工作区状态（分支、dirty 数、变更样本）
- `boundary_check` — 边界校验（模块任务会校验所有改动是否在允许目录内，有越界标记为失败）
- `lint` — lint 结果列表
- `tests` — 测试结果列表
- `verification_summary` — 验证摘要（你填了什么验证结果）
- `risk_note` — 残留风险评估
- `memory_write_template` — 带格式的记忆模板，含三节：改了什么 / 验证了什么 / 是否还有残留风险

**收尾后必须 `memory_write(agent="<agent名>")` 落一条项目记忆**，让后续 agent 可追溯。

### 工具用途边界

| 工具 | 用途 | 边界 |
|------|------|------|
| `clear_log(module, all, keep_state)` | 清空日志文件，排查问题时清老日志以确认新日志无错误。默认保留 `.backend.port` / `.watchdog.pid` | 不要在正常调试时滥用；清完记得 `tail_log` 确认 |
| `tail_log(module, lines)` | 查看日志尾部。排查问题第一手工具 | 上限 500 行；模块名映射失败时会回退到 uvicorn 主日志 |
| `workspace_reset(confirm, scope)` | 一键重置工作区数据（桌面/知识库/文件）。需 `confirm="RESET"` | 高危操作，不可撤销。只应在 sandbox 测试后清理时用 |
| `probe(method, path, body)` | 打后端任意 HTTP 接口，自动登录 | 接口验证优先用此工具，少写测试脚本搭场景 |
| `call_capability(module, action, params)` | 调模块能力（跨模块调用入口） | 模块间互调唯一通路。不走直接 import |
| `sql(query)` | 只读 SQL 查询（SELECT/WITH/EXPLAIN/SHOW/DESCRIBE） | 禁止 INSERT/UPDATE/DELETE/DROP。数据库巡检和排查用 |
| `web_read(url)` | 读网页，返回 markdown 正文 | 仅读不写 |
| `start_frontend()` | 启动前端开发服务器 | 等价 `cd frontend && npm run dev`，服务已启动时不应重复调用 |

## 工具清单

### 全景感知
| 工具 | 说明 |
|------|------|
| `brief()` | 项目全景: README + 最近变更 + 投递箱待处理 + 最近 Git 提交 + 最近项目记忆(带 agent) |

### 工作流入口
| 工具 | 说明 |
|------|------|
| `plan_task(description, task_type, module_key)` | **【标准工作流入口】** 任务开始前调此工具，自动预采证据并生成结构化计划（问题理解、required_evidence 清单、modification_boundary、verification_plan、workflow 步骤） |

### 代码探索与修改验证
| 工具 | 说明 |
|------|------|
| `code_explore(query)` | codegraph 探索: 查符号/调用链/影响面 |
| `code_node(symbol)` | codegraph 查符号或文件定义 |
| `code_impact(path)` | codegraph 查文件改动的影响面 |
| `quick_fix_preview(path, old_text, new_text, start_line, end_line, expected_old_text_sha256)` | 预览精准补丁: 精确 old_text 替换, 不写盘 |
| `quick_fix_patch / apply_patch(path, old_text, new_text, start_line, end_line, expected_old_text_sha256)` | 应用精准补丁: 同预览校验, 唯一命中后原子写盘 |
| `lint(path, diff)` | ruff 静态检查 Python 文件；`diff=true` 只预览 ruff 建议 diff，不写盘 |
| `finish_task(summary, agent, lint_paths, test_targets, module_key, verification_summary, risk_note)` | **【收工检查】** 汇总 Git dirty + 边界检查(模块路径越界校验) + 可选 lint/test + 风险评估 + 生成 memory_write 留痕模板；不提交、不写记忆 |

### 接口与能力查询
| 工具 | 说明 |
|------|------|
| `routes(filter)` | 从 openapi.json 查端点(方法/路径/参数) |
| `capabilities(module)` | 扫描模块 manifest.json 查准能力+参数 |
| `db_schema(table)` | 查数据库表结构(列名/类型/nullable) |

### 系统探测
| 工具 | 说明 |
|------|------|
| `probe(method, path, body)` | 自动登录后打后端任意 HTTP 接口 |
| `call_capability(module, action, params)` | 调模块能力(跨模块) |
| `tail_log(module, lines)` | 查看模块日志尾部 |
| `clear_log(module, all, keep_state)` | 清空项目日志文件, 默认保留 `.backend.port` / `.watchdog.pid` |
| `sql(query)` | 只读 SQL 查询(SELECT/WITH/EXPLAIN) |
| `web_read(url)` | 读网页返回 markdown 正文 |

### 记忆与归因
| 工具 | 说明 |
|------|------|
| `memory_search(query, k)` | 语义+关键词搜索项目记忆 |
| `memory_write(type, title, body, tags, agent)` | 写入项目记忆, agent 字段用于归因 |
| `memory_recent(n)` | 最近 N 条记忆 |

### 测试 / 回归
| 工具 | 说明 |
|------|------|
| `run_test(target, timeout)` | 跑单个测试；自动兼容 `backend/tests/...`、`tests/...`、绝对路径，返回结构化结果 |
| `sanity_check()` | 规范检查: 前端端口 + 后端健康 + 模块导入 + 知识图谱 |
| `smoke_all()` | 一键全模块回归红绿矩阵(也可 `python3.14 dev_toolkit/smoke.py`)。**注:当前断言偏浅有假绿/假红,待"修smoke可信度"批修准** |
| `start_frontend()` | 启动前端开发服务器（等价 `cd frontend && npm run dev`） |

### 工作区管理
| 工具 | 说明 |
|------|------|
| `workspace_audit()` | 盘点工作区数据现状: 桌面文件/知识库表/上传文件/污染样本 |
| `workspace_reset(confirm, scope)` | 一键重置工作区数据(需 confirm=RESET, scope=all/desktop/knowledge/files) |
| `knowledge_noise_report()` | 扫描知识库相关的测试/烟雾/验收污染文件 |
| `knowledge_cleanup_noise()` | 删除知识库相关的测试/烟雾/验收污染文件 |

## 工作流示例

### 代码修改类任务

```
step  agent 工具                                            产出
────  ──────────────────────────────────────────             ──────────────────
1     brief()                                                项目全景
2     plan_task("修复知识库搜索返回空", "code_change", "knowledge")    结构化计划
3     code_explore("knowledge search list_templates")        相关代码
4     code_node("KnowledgeSearchService")                    关键符号定义
5     code_impact("modules/knowledge/backend/service.py")    影响面
6     routes("knowledge")                                    相关端点
7     capabilities("knowledge")                              模块能力
8     db_schema("knowledge")                                 表结构
9     基于证据确定改动方案                                   方案
10    quick_fix_preview / quick_fix_patch                    预览/落盘
11    git diff --name-only                                   边界检查
12    lint(path)                                             静态检查
13    run_test(target)                                       跑测试
14    probe / call_capability                                接口验证
15    tail_log("knowledge")                                  日志确认
16    finish_task(..., module_key="knowledge")               收工汇总
17    memory_write(agent="opencode")                         留痕
```

### 排查类任务

```
step  agent 工具                                            产出
────  ──────────────────────────────────────────             ──────────────────
1     plan_task("排查登录失败", "investigation")              结构化计划
2     tail_log("auth")                                       看登录日志
3     probe("POST", "/api/login", '{"username":"...","password":"..."}')  复现
4     db_schema("users")                                     查用户表结构
5     sql("SELECT ... FROM users WHERE ...")                 查数据
6     code_explore("login authenticate")                     查代码
7     定位根因后写入 memory_write(type="gotcha")              留痕
```

## CodeGraph + Quick Fix 工作流

`quick_fix_preview` / `quick_fix_patch` 是给 CodeGraph 定位后的快速修复刀口:

1. 用 `code_explore` / `code_node` 找到文件、符号、行号和影响面。
2. 从 CodeGraph 返回的源码中复制完整 `old_text` 块, 写出 `new_text`。
3. 先调 `quick_fix_preview` 看 unified diff。
4. diff 确认后调 `quick_fix_patch` 落盘。
5. 再跑 `code_impact` + `lint` / `run_test` / `probe` / `call_capability` 验证。

安全规则:
- 路径必须在仓库内, 且拒绝 `.git`、`node_modules`、`.venv`、`venv`、`__pycache__`、`后端`、`脚本`、`部署`、`_废弃` 等边界外/废弃路径。
- `old_text` 必须非空且唯一命中; 重复命中时必须补 `start_line`/`end_line` 收窄。
- 行号只做定位窗口, 真正写入以 `old_text` 精确匹配为准。
- 可传 `expected_old_text_sha256` 防止调用方传错原文块。
- 写盘使用临时文件 + replace 原子替换。

## 开发铁律

1. 每个开发 agent 开工先调 `brief()` 看全貌；然后调 `plan_task()` 生成计划。
2. 查代码优先 `code_explore`/`code_node`/`code_impact` (codegraph)。
3. 查准端点/能力/表用 `routes`/`capabilities`/`db_schema`。
4. **证据收集不齐不准改代码。**
5. 改完先 `lint` 静态查错；只想看自动修复建议时用 `lint(diff=true)`。
6. 验证用 `probe`/`call_capability` 打活系统；测试用 `run_test`。
7. 日志排查先用 `tail_log`，必要时 `clear_log` 清空后再 `tail_log` 确认。
8. **模块任务只允许改本模块目录**，跨模块调用必须走统一通路。
9. 收工必须：`finish_task`（含边界检查）→ `memory_write` 留痕。
