# 模块开发文档

## 模块目标

模块是桌面里的软件和插件。业务功能优先放入 `modules/`，不要塞进框架。

每个模块必须先在自己的 `sandbox/` 里完成独立开发和验收，再接入主桌面壳。

## 当前真实状态

- `modules/_template/` 已创建，包含标准 sandbox 模板和 runtime 中间层，新模块复制即用。
- `modules/ai-assistant/` 已有前端占位（`frontend/index.vue`），后端代码已从平台层清理，待按模块规范重建。
- 模块扫描链路：`scripts/scan-modules.js` 扫描 `modules/*/manifest.json`（跳过 `_` 开头目录），生成 `component-key-map.generated.ts`。
- 平台层已无业务模块代码：`backend/app/services/agent/` 和 `backend/app/services/knowledge/` 已删除，对应的 18 个 router 已移除。
- 模型网关保留为框架能力：`backend/app/gateway/`（原 `services/agent/gateway/`）。

## 新建模块流程

```bash
# 1. 复制模板
cp -r modules/_template modules/YOUR_MODULE_KEY

# 2. 替换占位符
#    MODULE_KEY          → your-module-key
#    MODULE_DISPLAY_NAME → Your Module Display Name
#    SANDBOX_PORT        → 唯一端口号

# 3. 开发
cd modules/YOUR_MODULE_KEY/sandbox
npm install
npm run dev

# 4. 集成验证
cd /path/to/frontend
npm run build
```

## 目标模块结构

```text
modules/{module_name}/
  manifest.json          ← 模块身份（名称、图标、权限、窗口规格、后端路由）
  frontend/              ← Vue 组件和业务逻辑
    index.vue            ← 入口组件
  backend/               ← (可选) Python FastAPI router
    router.py            ← export router = APIRouter(...)
  runtime/               ← 运行时中间层（从 _template 复制）
    index.ts             ← getApiUrl(), hasPermission(), getModuleSetting()
  sandbox/               ← 独立开发环境
    package.json
    vite.config.ts
    runtime.config.json
    index.html
    src/main.ts
    src/App.vue
  submodules/            ← (可选) 子模块
  test-data/             ← 测试数据（有来源、有标记、有清理）
  assets/                ← 静态资源
  module-docs/           ← 模块文档
  tests/                 ← 模块级测试
```

## 目标 sandbox 门禁

模块开发必须先完成 sandbox 自测，再接入主框架。

```text
modules/{module_name}/sandbox/
  index.html
  vite.config.ts
  runtime.config.json
  package.json
  src/main.ts
  src/App.vue
```

未通过 sandbox 的模块，不允许接入桌面壳。

### sandbox 模板不够用时

sandbox 是最小桌面壳。如果模块需要框架功能：

1. 从 `frontend/src/` 复制需要的代码到 sandbox 中
2. 常见需要复制的内容：shared composables、API helpers、UI 组件、auth mock
3. 在 `sandbox/package.json` 中添加额外依赖

## 模块间协作

多个模块可以同时独立开发——每个 sandbox 是独立 Vite 项目，有自己的端口，通过 proxy 连到同一个后端。互不依赖、互不干扰。

## 子模块规则

复杂模块可以拆子模块：

```text
modules/knowledge/submodules/catalog/
modules/knowledge/submodules/ingestion/
modules/knowledge/submodules/retrieval/
modules/knowledge/submodules/qa/
```

子模块由父模块扫描和管理，不进入桌面壳全局扫描。子模块要成为桌面应用，必须升级为顶层模块。

## Runtime 中间层

每个模块的 `runtime/index.ts` 提供：

- `getApiUrl(path)` — 构建完整 API URL
- `hasPermission(permission)` — 权限检查
- `getModuleSetting(key)` — 读取模块配置
- `getMode()` — sandbox / framework 模式

模块业务代码只通过 runtime 获取这些值，不硬编码路径。sandbox 模式读 `runtime.config.json`，framework 模式由桌面壳注入。

## 测试数据规则

- 有来源。
- 有标记。
- 有清理脚本。
- 用完清空。

## 文档规则

每个模块目录只保留一个长期 `README.md`。临时方案完成后必须合并回该模块 `README.md`，然后删除临时文档。
