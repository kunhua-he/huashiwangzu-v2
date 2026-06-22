# 华世王镞 V2 开发文档（总索引）

> 本文件是项目接手入口。新会话先读这里，再按任务类型进入框架、底层或模块文档。

## 本次盘点来源

本页依据 2026-06-22 的源文件与 Git 历史重写，优先级如下：

1. `git log --oneline -20`
2. `modules/*/backend/router.py` 的模块 docstring 与路由函数 docstring
3. `frontend/package.json`
4. `backend/app/config.py`
5. 模块 `manifest.json` 仅用于补充模块目录、入口、公开能力和文件关联信息

已确认的硬事实：最新 HEAD 为 `3d084a1`；前端是 Vue 3 + vue-router + Pinia + Vite；数据库底座是 PostgreSQL + pgvector；`modules/` 下当前有 26 个一级模块目录，其中 `_template` 是模块模板。

早前 GPT5.5 对比盘点可作为背景材料，但两处结论已按源文件纠正：前端不是原生 HTML；统一客户端/运行时客户端并非不存在。

## 项目定位

华世王镞 V2 是一个干净架构重建项目，不是在旧 Laravel/PHP 树上打补丁。目标形态是“桌面壳 + 平台服务层 + 可插拔业务模块”，服务 20-50 人内部企业业务场景。

```text
frontend/   桌面壳前端：登录、桌面、窗口、任务栏、启动器、模块加载、文件打开调度
backend/    平台服务层：API、鉴权、数据库、文件、任务、日志、模型网关、模块注册
modules/    业务模块和桌面应用：独立 sandbox 开发，经 manifest/runtime/API 接入主壳
```

V1 只作为只读参考：`../华世王镞_v1/`。缺能力时可以查 V1 行为，但必须按 V2 架构重建。

## 当前总览

| 项 | 当前事实 |
|----|----------|
| 最新提交 | `3d084a1 fix(agent): 修复P2P3拆分引入的engine import错误(handlers改裸import,否则overview/approvals/chat端点500)` |
| 前端 | Vue `^3.5.34` + vue-router `^5.1.0` + Pinia `^3.0.4` + Vite `^8.0.12` + TypeScript `~6.0.2` + Element Plus `^2.14.1` |
| 前端入口 | `frontend/src/main.ts` 挂载 Vue、Pinia、router 和权限指令；`frontend/src/App.vue` 只承载 `router-view` |
| 前端统一 API | `frontend/src/shared/api/index.ts` 使用 Axios，统一处理 `v2_auth_token`、401 自愈、错误上报和 `{success,data,error}` 响应 |
| 模块 runtime | 模块 runtime 提供 `auth/files/office/gateway/tasks/notifications/logs/settings/modules` 等 namespace；内部用 `authHeaders()` 携带 token |
| 后端 | FastAPI + SQLAlchemy async；平台入口与 router 注册见 `backend/app/main.py`、`backend/app/registry.py` |
| 配置 | `backend/app/config.py` 读取 `.env`，构造 `postgresql+asyncpg://...`，JWT 强制非空，默认 CORS 指向 `5173` |
| 实际后端端口 | 启动脚本和当前 `backend/logs/.backend.port` 指向 `33000`；`config.py` 的 `APP_PORT=30004` 不是当前 watchdog 启动口径 |
| 数据库 | PostgreSQL；pgvector 依赖在 `backend/requirements.txt`，记忆模块使用 `Vector(1024)` 并在初始化中 `CREATE EXTENSION IF NOT EXISTS vector` |
| 模块规模 | `modules/` 下 26 个一级目录：25 个业务/工具/查看器模块 + `_template` 模板；其中 19 个模块当前有后端 `router.py` |
| 统一响应 | 后端 router 普遍返回 `app.schemas.common.ApiResponse`，目标形态为 `{ "success": true, "data": ..., "error": ... }` |
| 代码索引 | 仓库已有 `.codegraph/`，改/查代码先用 CodeGraph；模块侧还有 `codemap` 能力用于影响面与边界检查 |

## 最近 20 条 Git 历史

最近提交集中在 Agent engine、治理、安全审计、docs-open、知识/记忆能力与若干工具回归修复。

```text
3d084a1 fix(agent): 修复P2P3拆分引入的engine import错误(handlers改裸import,否则overview/approvals/chat端点500)
a9ef748 fix(security): audit P2/P3收尾 - XSS/路径边界/异常契约/权限/拆文/文档
3d3f3c9 fix(terminal-tools): P0-3沙盒修复引入的回归——run_python无法启动
c6ccc42 fix: security audit P0/P1 — docs-open越权/run_python沙盒/共享写权限/数据完整性
f9dc567 feat(agent-governance): batch2 — per-agent config console + sensitive action approval + worker startup recovery
fa15994 feat(agent-governance): batch1 — gateway rectification + background tasks + cost governance
795ea11 chore(audit): 全模块去重治理就地修8项(codemap鉴权/manifest补齐/token key统一)
034a39a fix(agent): 移除批5复活的顶部ChatToolbar(撑崩布局),engine面板按钮移入侧边栏
6821cda feat(docs-open): 文档开放接口模块 - 令牌三件套+REST+嵌入编辑器+JSON中间层
3a14a82 批5 可观测：事件重放+单轮trace+admin调优面板
87de41e engine批4——韧性(compressor+模型fallback_chain+stuck_detector+全链路降级兜底)
a503388 docs: 主索引刷新到当前态(~26模块+engine+知识库五层) + 新增算法调优手册
f9d6815 fix(memory): 批3experience_memory两处致命bug——后端启动崩 + save崩
88212af 批3：experience_memory（成功经验快速通道 + 强化加权）
edf986c feat(agent): engine batch 1 — event sourcing base + engine shell + dynamic budget allocator
51843a5 fix: DeepSeekAdapter now extracts tool_calls + parallel tool execution in router
55a4ca3 feat(agent): 后台任务池 + 子Agent + 记忆集成
d7a71d2 fix(agent): skill_use args 容错 + final_clean_content 兜底 + 单测
0c5b932 fix(pdf-viewer): 文字层选区错位——补 --scale-factor + span 定位CSS
d05beda chore(deps): requirements 加 pytesseract(PDF扫描件文字层词坐标用)
```

## 前端真实状态

`frontend/package.json` 明确显示这是现代 Vue 应用，不是原生 HTML：

- 运行：`npm run dev` 走 Vite。
- 构建：`npm run build` 会先执行 `node scripts/scan-modules.js`，再复制 PDF worker，执行 `vue-tsc -b` 和 `vite build`。
- 路由：`frontend/src/app-entry/router/index.ts` 使用 `createRouter(createWebHistory())`，登录页在 `/`，桌面页在 `/desktop`。
- 状态：`frontend/src/platform/stores/user.ts` 使用 Pinia 管理登录态和当前用户。
- UI：Element Plus、Element Plus icons、Fluent SVG icons；PDF.js、Three.js、marked、highlight.js、DOMPurify 等用于文档、3D 图谱、Markdown 与安全渲染。
- 模块加载：`frontend/scripts/scan-modules.js` 扫描模块 manifest，生成 `frontend/src/desktop/app-registry/component-key-map.generated.ts` 与模块图标映射。

## 后端与配置真实状态

`backend/app/config.py` 的关键事实：

- 数据库默认连接参数：`DB_HOST=127.0.0.1`、`DB_PORT=5432`、`DB_USER=postgres`、`DB_NAME=huashiwangzu_v2`，密码必须从 `.env` 或环境变量提供。
- `DATABASE_URL` 使用 `postgresql+asyncpg`。
- `JWT_SECRET` 必须设置，空值会在配置校验阶段拒绝启动。
- JWT 算法为 `HS256`，过期时间默认 `1440` 分钟。
- CORS 默认允许 `http://127.0.0.1:5173` 和 `http://localhost:5173`。
- 模型相关配置包含 watchdog、本地模型根目录、MIMO、DeepSeek、GPTStore 中转站等。

运行口径以脚本为准：`scripts/start_backend.sh` 和 `scripts/backend_watchdog.sh` 固定使用 `33000`，并把实际端口写入 `backend/logs/.backend.port`。

## 模块地图

### AI 与知识中枢

| 模块 | 后端 | 盘点摘要 |
|------|------|----------|
| `agent` | 有 | AI 助手，对话、SSE、工具发现、系统/企业/个人提示词、会话、管理回放、overview、敏感操作审批；最近 HEAD 修复了 handlers import 导致的管理端 500。 |
| `memory` | 有 | 记忆保存、召回、列表、删除、融合、重思考、替换、插入、dream 自优化；使用 pgvector 1024 维向量承载语义召回和经验匹配。 |
| `knowledge` | 有 | 知识库文档注册、解析、原始采集、页级融合、文件画像、实体图谱、跨文件关系、全链路 pipeline、进度查询、搜索与治理接口。 |
| `codemap` | 有 | 代码地图；docstring 声明 HTTP 端点和跨模块能力，包括 get_file、impact、check_boundary、module_map、search、stats、rebuild、文件锁和反馈记录。 |

### 工具与自动化

| 模块 | 后端 | 盘点摘要 |
|------|------|----------|
| `terminal-tools` | 有 | 用户工作区内执行 shell、写/读文件、列目录、publish/import、run-python、chart；最近历史包含 sandbox 和 run_python 回归修复。 |
| `desktop-tools` | 有 | 桥接框架文件/应用能力给 Agent：列文件、搜索文件、读文件、列应用；查询按 owner 隔离。 |
| `web-tools` | 有 | DuckDuckGo HTML 搜索与网页正文抓取，无 API key，带 SSRF 防护。 |
| `office-gen` | 有 | 生成 docx/xlsx/pptx/pdf，转换 office 文件；注册 5 个跨模块能力。 |
| `image-gen` | 有 | 通过框架网关/GPTStore 生成图片，provider 未配置时有占位降级。 |
| `scheduler` | 有 | 创建、列出、取消定时任务。 |
| `im` | 有 | 站内消息：会话列表、消息、发送、标记已读、未读数、用户列表；manifest 暴露 notify/send。 |
| `docs-open` | 有 | 文档开放接口 facade，仿腾讯文档三件套 token + REST + 嵌入编辑器 + JSON 中间层；最近历史包含越权修复。 |

### 文件解析、查看与编辑

| 模块 | 后端 | 盘点摘要 |
|------|------|----------|
| `pdf-parser` | 有 | 注册 parse 能力，把 PDF 转统一内容块。 |
| `docx-parser` | 有 | 注册 parse 能力，把 DOCX 转统一内容块。 |
| `pptx-parser` | 有 | 注册 parse 能力，把 PPTX 转统一内容块。 |
| `xlsx-parser` | 有 | 注册 parse 能力，把 XLSX/CSV 转统一内容块。 |
| `text-parser` | 有 | 注册 parse 能力，把 TXT/MD 转统一内容块。 |
| `image-vision` | 有 | 注册 describe 能力，通过视觉模型描述图片。 |
| `excel-engine` | 有 | 在线表格编辑器，docstring 标注为旧表格 API 的 1:1 迁移入口，支持 parse/open/dispatch/edit/style/clipboard/table/state/export/download。 |
| `pdf-viewer` | 无 | PDF 查看器，支持 `pdf` 文件关联。 |
| `doc-viewer` | 无 | 文档查看器，支持 `docx/doc` 文件关联。 |
| `ppt-viewer` | 无 | 演示文稿查看器，支持 `pptx/ppt` 文件关联。 |
| `image-viewer` | 无 | 图片查看器，支持 png/jpg/jpeg/gif/bmp/webp/svg/ico。 |
| `text-editor` | 无 | 文本编辑器，支持 txt/md/log/json/csv/yaml/yml/xml/ini/cfg，除 csv 外多数字段可编辑。 |

### 样板

| 模块 | 后端 | 盘点摘要 |
|------|------|----------|
| `hello-world` | 无 | 最小前端样板，用于验证模块扫描、桌面加载和 runtime gateway 调用。 |
| `_template` | 无 | 新模块模板，包含 manifest、runtime、frontend 和 sandbox 骨架；不是业务模块。 |

## 架构边界

必须长期保持三层边界：

```text
frontend/   桌面壳与平台前端能力
backend/    桌面壳后端与平台公共服务层
modules/    业务模块、工具模块、查看器和编辑器
```

模块任务只允许改 `modules/{当前模块}/`。模块可以调用框架公开能力，但不能修改 `backend/app/`、`frontend/src/` 或其他模块。跨模块调用必须走统一通路：前端 `platform.modules.call/capabilities`，后端 `/api/modules/call` + capability registry，禁止互相 import 代码或直接读写对方表。

## 开发入口

按任务类型先读对应文档：

1. 改桌面壳、窗口系统、模块加载、前端平台能力：`开发文档/01_框架开发文档/README.md`
2. 改后端平台、数据库、权限、任务、文件、模型网关：`开发文档/02_底层开发文档/README.md`
3. 改模块、新建模块、处理模块边界：`开发文档/03_模块开发文档/README.md`
4. 改具体模块：先读 `modules/{module}/README.md`，再读该模块源码
5. 调 Agent engine：读 `开发文档/算法调优手册.md` 和 `modules/agent/README.md`
6. 查历史原因：读 `开发文档/变更历史.md`

## 默认验证

文档改动无需跑完整测试。代码改动按影响面选择验证：

```bash
# 后端平台或后端模块改动
cd backend && .venv/bin/python -m pytest

# 前端或模块前端改动
cd frontend && npm run build

# 模块扫描
cd frontend && npm run scan:modules
```

改代码前优先使用 CodeGraph；需要模块边界或影响面时再用 codemap。当前工作树已有未跟踪目录 `backend/data/.tmp_uploads/`，它不是本次文档盘点产物，处理 git 时不要误删或误提交。
