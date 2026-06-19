# Excel Engine Module — 文件引擎标杆

## 模块说明

Excel 编辑器模块，为 V2 桌面壳提供类似 WPS 的在线表格编辑体验。作为"文件引擎"系列的第一个标杆模块，沉淀通用架构供后续格式（docx/pdf/pptx）复用。

## 文件引擎统一模式

```
解析层（文件 ⇄ 状态，借内核）
    ↓
状态层（数据库持久化 + 操作历史，自研）
    ↓
编辑器前端（网格渲染 + 交互，UI 全自研可控）
    ↓
导出层（状态 → 文件，借内核）
    ↓
解析技能（跨模块能力，注册到框架）
```

### 层职责

| 层 | 目录 | 技术 | 说明 |
|---|------|------|------|
| 解析层 | `backend/engine/` | `openpyxl` + 自研 XML 解析 | XLSX/CSV 解析为统一状态结构 |
| 状态层 | `backend/state/` | Python dict + PostgreSQL（`excel_*` 表） | 单元格值、样式、合并、历史、快照 |
| 编辑器前端 | `frontend/` | Vue 3 自研网格组件 | 网格渲染、编辑、工具栏、右键菜单、历史面板 |
| 导出层 | `backend/engine/xlsx_generator.py` | `openpyxl` 生成 | 状态 → XLSX/CSV 文件 |
| 解析技能 | `backend/router.py` → `register_capability` | 框架跨模块能力注册 | 供 Agent / 知识库调用 |

### 架构铁律

1. **UI 全自研**：不整体依赖任何第三方编辑器组件库（网格、工具栏、菜单全部自建）
2. **内核可借**：解析/生成算法可借开源库（`openpyxl`），但数据结构 1:1 对照已验证实现
3. **命令式历史**：每次写操作前记录完整快照，撤销/重做通过快照恢复（非快照差异）
4. **API 驱动渲染**：每次编辑 → 后端写状态 + 记录历史 → 前端只渲染受影响的元素
5. **表前缀隔离**：业务表 `excel_*` 前缀，无数据库外键

## 目录结构

```
modules/excel-engine/
  manifest.json          ← 模块清单（key, icon, 窗口规格, 后端路由, 公开能力）
  frontend/              ← 前端 Vue 组件
    index.vue            ← 入口组件
    components/
      ExcelGrid.vue      ← 自研网格渲染（列头、行号、单元格、合并、编辑）
      ExcelToolbar.vue   ← 工具栏（加粗/颜色/对齐/字体/字号/保存/撤销）
      ContextMenu.vue    ← 右键菜单
      HistoryPanel.vue   ← 操作历史面板
      address-util.ts    ← 地址工具（A1 解析、合并映射）
  backend/               ← Python FastAPI 后端
    router.py            ← 统一 API 路由 + 能力注册
    models.py            ← SQLAlchemy 模型（8 表：workbook/sheet/cell/col/row/history/redo/version）
    engine/              ← 解析/生成引擎
      xlsx_parser.py     ← XLSX 解析入口
      csv_parser.py      ← CSV 解析入口
      xlsx_generator.py  ← XLSX/CSV 生成
      color_parser.py    ← 颜色解析（主题色/索引色/tint）
      style_parser.py    ← 样式解析（字体/填充/边框/对齐）
      shared_strings.py  ← 共享字符串表
      workbook_parser.py ← 工作簿列表
      sheet_parser.py    ← 子表数据解析
    state/               ← 状态管理
      manager.py         ← 内存状态 + 单元格工具
      db_ops.py          ← 数据库持久化 + 历史/快照/撤销恢复
    table/               ← 业务逻辑
      edit.py            ← 编辑（输入/批量/清除/超链接/公式）
      style_ops.py       ← 样式操作
      clipboard.py       ← 剪贴板（复制/粘贴）
      row_col.py         ← 行列操作（插入/删除/合并/排序）
    tool/                ← 工具函数
      address.py         ← A1 地址解析
      formula.py         ← 公式计算（SUM/AVERAGE/COUNT/MAX/MIN/算术）
      config.py          ← 配置常量
  runtime/               ← 运行时 SDK
    index.ts             ← platform.files/office/gateway/modules 等
  sandbox/               ← 独立开发环境
```

## 后端 API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/excel-engine/health` | GET | 健康检查 |
| `/api/excel-engine/parse` | POST | 解析 xlsx/csv 文件为状态 |
| `/api/excel-engine/open` | POST | 打开文件（解析 + 入库） |
| `/api/excel-engine/dispatch` | POST | 统一调度（兼容旧 API 模式） |
| `/api/excel-engine/edit` | POST | 编辑单元格 |
| `/api/excel-engine/style` | POST | 修改单元格样式 |
| `/api/excel-engine/clipboard` | POST | 剪贴板复制/粘贴 |
| `/api/excel-engine/table` | POST | 行列操作（插入/删除/合并/排序） |
| `/api/excel-engine/state` | POST | 状态操作（读取/撤销/恢复/历史） |
| `/api/excel-engine/export` | POST | 导出（XLSX/CSV/数据） |
| `/api/excel-engine/download/{state_key}` | GET | 下载 XLSX 文件 |

响应格式：`{"success": true/false, "data": ..., "error": ...}`

## 数据库表

| 表名 | 说明 |
|------|------|
| `excel_workbooks` | 工作簿 |
| `excel_sheets` | 子表 |
| `excel_cells` | 单元格值 + 样式 + 合并信息 |
| `excel_col_widths` | 列宽 |
| `excel_row_heights` | 行高 |
| `excel_history` | 操作历史（含快照） |
| `excel_redo_stack` | 撤销恢复栈 |
| `excel_versions` | 版本快照 |

## 能力注册

```python
register_capability("excel-engine", "parse", handler,
    description="Parse XLSX/CSV files into cell data structure",
    parameters={"file_id": {"type": "int"}},
    min_role="viewer")
```

## 开发与测试

```bash
# 后端测试（需要 backend/.venv）
cd modules/excel-engine/sandbox
python3 test_module.py

# 框架测试
cd backend && .venv/bin/python -m pytest

# sandbox 前端开发
cd modules/excel-engine/sandbox
npm install
npm run dev
```

## 与 V1 对照

| 模块 | V1 (PHP) | V2 (Python+Vue) |
|------|----------|-----------------|
| 引擎层 | `引擎/xlsx解析.php` + 子解析器 6 个 | `backend/engine/` 7 个文件 |
| 状态层 | `表格/状态*.php` 10 个 trait + MySQL 8 表 | `backend/state/` 2 个文件 + PostgreSQL 8 表 |
| 业务层 | `表格/编辑.php` + `样式.php` + 剪贴板/行列 | `backend/table/` 5 个文件 |
| 工具层 | `工具/公式.php` + `地址工具.php` + `配置.php` | `backend/tool/` 3 个文件 |
| 前端 | 原生 JS + iframe 嵌入（`编辑器.js` + 面板/历史面板） | Vue 3 组件（`frontend/` 5 个文件） |
| UI | PHP 渲染 + CSS 内联 | 自研 Vue 组件，完全可控 |
| 数据库 | MySQL 8 表 | PostgreSQL 8 表 |
| 跨模块 | 无 | `register_capability` 注册解析能力 |

## 扩展指南

其他格式（docx/pdf/pptx）按此模式扩展：

1. 复制 `modules/excel-engine/` 为 `modules/{format}-engine/`
2. 替换 `backend/engine/` 为对应格式的解析生成（内核可借开源）
3. 替换 `backend/state/` 为对应格式的状态结构
4. `frontend/` 重写对应的编辑器 UI（全自研）
5. 修改 `manifest.json` 的 key/icon/supported_formats
6. 运行 `cd backend && .venv/bin/python -m pytest` 确认框架不受影响
