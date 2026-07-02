# 项目工具台 MCP Server

开工先连我。`python3.14 dev_toolkit/server.py` (stdio), 注册在 `.mcp.json`。

通过 MCP 协议暴露项目开发加速工具, 供 AI agent 直接调用。

## 组件化结构

`server.py` 只做 MCP 启动、通用上下文和顶层路由。新增工具优先拆成独立组件：

```text
dev_toolkit/{domain}_tools.py
  ├─ tool_definitions()  # 返回本组件 Tool schema
  ├─ handles_tool(name)  # 判断是否处理某个工具名
  └─ handle_tool(repo_root, name, arguments)  # 组件内部分发
```

主文件只负责：

```python
*domain_tool_definitions()
elif domain_handles_tool(name):
    result = await domain_handle_tool(REPO_ROOT, name, arguments)
```

不要继续把大段 schema 和业务实现堆进 `server.py`。

当前组件：

| 组件 | 负责工具 |
|------|----------|
| `mailbox_tools.py` | `写封信`、`mailbox_write_letter`、`mailbox_create_delivery_bundle`、`mailbox_check_delivery_bundle` |
| `memory_tools.py` | `memory_search`、`memory_write`、`memory_recent`、`mcp_feedback`、`mcp_feedback_summary` |
| `worktree_tools.py` | `worktree_guard` |
| `tool_usage_tools.py` | `tool_usage_stats` + 全局工具调用统计落盘 |
| `code_tools.py` | `code_explore`、`code_node`、`code_impact`、`quick_fix_preview`、`quick_fix_patch`、`apply_patch`、`lint`、`run_test` |
| `edit_tools.py` | `batch_quick_fix_preview`、`batch_quick_fix_apply`、`edit_recipe_catalog`、`edit_recipe_preview`、`edit_recipe_apply` |
| `insight_tools.py` | `mcp_self_check`、`dev_toolkit_architecture_audit`、`agent_activity_report` |

## 标准工作流（所有任务必须遵守）

### 工作流总览

```
brief (全景理解)
  → plan_task (生成计划 + 预采证据)
    → worktree_guard (确认 dirty / 边界 / 未跟踪文件)
    → 按 required_evidence 逐一收集证据
      → 制定修改方案
        → quick_fix_preview / patch 执行修改
          → lint + run_test + probe + tail_log 验证
            → finish_task (汇总 + 边界检查 + 风险评估，内部复用 worktree_guard)
              → memory_write (留痕归因)
                → mcp_feedback (工具体验反馈)
                  → mailbox_create_delivery_bundle / mailbox_check_delivery_bundle (需要回信时生成并检查五件套)
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

#### 阶段 3.5：工作区边界确认 → `worktree_guard`

修改前后都建议调用，尤其是 dirty 工作区和模块任务：

```text
worktree_guard(module_key="knowledge")
worktree_guard(allowed_prefixes="backend/app,dev_toolkit,开发文档")
```

它会统计 git dirty 文件，**包含 untracked 文件**，按路径分组，并检查：
- 是否越出 `module_key` 或 `allowed_prefixes`
- 是否碰到 `.git`、`node_modules`、虚拟环境、废弃目录等 forbidden 前缀
- dirty 样本是否来自本任务范围

#### 阶段 4：执行修改
基于证据确定具体改动，用 `quick_fix_preview` 预览 → `quick_fix_patch` 落盘。

批量确定性改动可用 `batch_quick_fix_preview` / `batch_quick_fix_apply`。它是轻量编辑 worker，不是子代理，也不会请求 LLM：MCP 只接收明确的 `old_text/new_text` 操作列表，并发预检 diff，全部安全后再写盘。默认拒绝同一文件并行多次写入，避免互相覆盖；确需同文件多处修改时可拆成一次更大的 `old_text` 替换，或显式 `allow_same_file=true` 顺序执行。

常见模式可用 `edit_recipe_catalog` 查看 recipe，再用 `edit_recipe_preview/apply` 执行。recipe 仍然会落到 quick_fix 的唯一命中、安全边界、原子写盘规则上。

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

#### 阶段 6：收尾留痕 → `finish_task` + `memory_write` + `mcp_feedback` + `mailbox_create_delivery_bundle`

**`finish_task(summary, agent, lint_paths, test_targets, module_key, verification_summary, risk_note)`**

收尾检查，不是仅做摘要。输出包含：
- `git` — Git 工作区状态（分支、dirty 数、变更样本）
- `boundary_check` — 边界校验（复用 `worktree_guard`，包含 untracked 文件；模块任务会校验所有改动是否在允许目录内，有越界标记为失败）
- `lint` — lint 结果列表
- `tests` — 测试结果列表
- `verification_summary` — 验证摘要（你填了什么验证结果）
- `risk_note` — 残留风险评估
- `memory_write_template` — 带格式的记忆模板，含三节：改了什么 / 验证了什么 / 是否还有残留风险
- `mailbox_delivery_template` — 回信五件套模板，需交付到邮箱时直接传给 `mailbox_create_delivery_bundle`

**收尾后必须 `memory_write(agent="<agent名>")` 落一条项目记忆**，让后续 agent 可追溯。

**收尾后也必须 `mcp_feedback(agent, task_summary, rating, smoothness, tools_used, friction, missing_tools, upgrade_suggestions, remove_or_merge_suggestions)` 留一条工具体验反馈**。反馈会写入 `开发文档/项目记忆/` 下的结构化 Markdown，方便后续升级项目工具台。

如果任务来自邮箱投递信，或用户要求“回信/五件套”，收尾后调用：

```text
mailbox_create_delivery_bundle(task_name, summary, changed_files, verification_results, risks, ...)
mailbox_check_delivery_bundle(task_name)
```

不要手工自由发挥五件套结构；标准文件固定为 `交付报告.md`、`修改文件清单.md`、`验收命令结果.md`、`剩余风险.md`、`元信息.json`。

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
| `tool_usage_stats(limit, reset, confirm)` | 查看项目工具台 MCP 工具调用热度 | 统计文件在 `backend/logs/tool_usage_stats.json`，可用于清理低价值工具和发现高频工作流 |
| `mcp_feedback(agent, task_summary, rating, smoothness, tools_used, friction, missing_tools, upgrade_suggestions, remove_or_merge_suggestions)` | 收工工具体验反馈，写入结构化 Markdown 项目记忆 | 必填轻量反馈：本次是否顺畅、缺什么、建议升级/移除什么 |
| `mcp_feedback_summary(limit)` | 汇总最近工具体验反馈 | 升级工具台前先看：平均评分、最新反馈、卡点和升级建议 |
| `mailbox_write_letter(target, category, title, body, required_docs, delivery_mode, overwrite)` | 标准化写投递信到邮箱/投递箱 | 自动补系统指令、必读文档、交付要求和收件箱路径；旧别名 `写封信` 也走同一规范 |
| `mailbox_create_delivery_bundle(task_name, summary, changed_files, verification_results, risks, ...)` | 生成回信标准五件套 | 写入邮箱/收件箱/{任务名}/，固定生成五个文件 |
| `mailbox_check_delivery_bundle(task_name)` | 检查回信五件套齐全性 | 校验五个文件存在，并检查 `元信息.json` 必填字段 |

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
| `batch_quick_fix_preview(operations, max_workers)` | 并发预览多个精准替换, 只读不写盘, 不调用 LLM |
| `batch_quick_fix_apply(operations, max_workers, lint_paths, test_targets)` | 并发应用多个精准替换: 先全量预览, 全部通过后写盘, 可选 lint/test |
| `edit_recipe_catalog()` | 列出确定性精准编辑 recipe |
| `edit_recipe_preview / edit_recipe_apply(recipe, parameters, lint_paths, test_targets)` | 用 recipe 生成精准替换并预览/应用, 常见场景包括 exact_replace、insert_after、replace_between_markers |
| `lint(path, diff)` | ruff 静态检查 Python 文件；`diff=true` 只预览 ruff 建议 diff，不写盘 |
| `worktree_guard(module_key, allowed_prefixes, forbidden_prefixes, include_untracked)` | 开工/收工边界守卫：统计 dirty 文件(含 untracked)、按路径分组、校验模块/允许路径/禁止路径 |
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
| `tool_usage_stats(limit, reset, confirm)` | 工具调用热度统计：按调用次数排序，返回成功/失败次数、平均耗时、最近调用时间；`reset=true` 需 `confirm="RESET"` |
| `mcp_feedback(agent, task_summary, rating, smoothness, tools_used, friction, missing_tools, upgrade_suggestions, remove_or_merge_suggestions)` | 收工反馈本次 MCP 是否顺畅、有无缺失能力和升级/移除建议；生成 Markdown 反馈记录 |
| `mcp_feedback_summary(limit)` | 汇总最近 MCP 反馈 Markdown，升级工具台前用它找高频卡点和建议 |
| `mcp_self_check(include_tools)` | MCP 自检: 工具数、组件覆盖、重复工具名、长文件、延迟加载提示 |
| `dev_toolkit_architecture_audit()` | 工具台组件化架构审计, 用于继续拆大文件和找维护风险 |
| `agent_activity_report(agent, limit)` | 按 agent 聚合工具反馈、声明使用工具、邮箱交付元信息和升级建议 |

### 邮箱投递与回信
| 工具 | 说明 |
|------|------|
| `mailbox_write_letter(target, category, title, body, required_docs, delivery_mode, overwrite)` | 标准化写投递信到 `华世王镞_v2邮箱/投递箱/`，自动补系统指令、必读文档、交付要求和收件箱目录 |
| `写封信(target, category, title, body, note)` | 兼容旧别名，内部已转到 `mailbox_write_letter` 的标准格式 |
| `mailbox_create_delivery_bundle(task_name, summary, changed_files, verification_results, risks, key_design, data_stats, ...)` | 标准化生成回信五件套到 `华世王镞_v2邮箱/收件箱/{任务名}/` |
| `mailbox_check_delivery_bundle(task_name)` | 检查五件套是否齐全，验证 `元信息.json` 必填字段 |

### 测试 / 回归
| 工具 | 说明 |
|------|------|
| `run_test(target, timeout)` | 跑单个测试；自动兼容 `backend/tests/...`、`tests/...`、绝对路径，返回结构化结果 |
| `sanity_check()` | 规范检查: 前端端口 + 后端健康 + 模块导入 + 知识图谱 |
| `smoke_all(skip_ui)` | 一键全模块回归红绿矩阵(也可 `python3.14 dev_toolkit/smoke.py`) |
| `release_gate(skip_ui)` | **发布前 gate**：聚合 health/system-status/smoke/队列审计/sandbox 矩阵，输出 BLOCKER/DEBT/PASS |
| `module_sandbox_matrix(check)` | 模块 sandbox 验收矩阵：列出全部模块的 sandbox/test/可运行状态，`--check` 运行 auto-runnable 用例 |
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
11    worktree_guard(module_key="knowledge")                 边界检查(含 untracked)
12    lint(path)                                             静态检查
13    run_test(target)                                       跑测试
14    probe / call_capability                                接口验证
15    tail_log("knowledge")                                  日志确认
16    finish_task(..., module_key="knowledge")               收工汇总(内部复用 worktree_guard)
17    memory_write(agent="opencode")                         留痕
18    mcp_feedback(agent="opencode", ...)                    工具体验反馈
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

多文件同类小改用 `batch_quick_fix_preview` / `batch_quick_fix_apply`。它只做确定性文本编辑，不会开子代理，也不会把任务再发给 LLM；适合“我已经知道这些文件里这几段代码要替换成什么”的场景。

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
9. 开工/收工边界检查优先用 `worktree_guard`，不要只靠 `git diff --name-only`。
10. 收工必须：`finish_task`（含边界检查）→ `memory_write` 留痕 → `mcp_feedback` 工具体验反馈。
11. `mcp_feedback` 必须实话实说：顺畅写顺畅，卡住写卡住；没有建议也要写“无”。
12. 升级工具台前先看 `tool_usage_stats` + `mcp_feedback_summary`：高频工具继续打磨，高频卡点优先修，低频/误导工具合并、降级或移除。
13. 邮箱任务必须用 `mailbox_write_letter` 投递，用 `mailbox_create_delivery_bundle` + `mailbox_check_delivery_bundle` 回信，不再手工拼五件套。
