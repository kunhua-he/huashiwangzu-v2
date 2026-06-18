# 文件夹 UI 重构方案

> 状态：草稿 | 日期：2026-06-18

## 1. 现状分析

当前文件夹打开后的 UI 由 `frontend/src/platform/components/apps/desktop/index.vue` 及其子组件构成：

```text
frontend/src/platform/components/apps/desktop/
├── index.vue                          ← 主布局容器
└── file-manager/
    ├── file-manager-header.vue        ← 标题 + 操作按钮 + 面包屑
    ├── file-manager-sidebar.vue       ← 桌面/回收站入口 + 当前位置 + 统计
    ├── file-manager-content.vue       ← Grid/List 双视图文件列表
    ├── file-manager-inspector.vue     ← 右侧详情面板
    ├── use-file-manager-state.ts      ← 状态管理逻辑
    └── types.ts                       ← 类型定义
```

当前布局为 **四栏结构**：

```
┌── Header（标题 + 面包屑 + 操作按钮）──────────────────────┐
├── Sidebar ──┬── Main（toolbar + content）──┬── Inspector ──┤
│  桌面/回收站  │  视图切换 + 文件列表           │  详情面板      │
│  当前位置     │                             │               │
│  统计信息     │                             │               │
└─────────────┴─────────────────────────────┴───────────────┘
```

### 现有问题

| # | 问题 | 说明 |
|---|------|------|
| 1 | 右侧 Inspector 常驻浪费空间 | 占用 260px 宽度，Windows 资源管理器无此面板，详情通过右键→属性查看 |
| 2 | 侧栏功能单薄 | 仅两个按钮 + 文本，不是真正的导航树 |
| 3 | 列表视图无列头 | 没有 Name / Date / Type / Size 列头，无法排序 |
| 4 | 无地址栏 | 面包屑为独立按钮拼接，不可编辑，不可复制路径 |
| 5 | 无搜索入口 | 没有在当前文件夹内搜索的能力 |

---

## 2. 设计目标

参照 Windows 10/11 文件资源管理器，重构为 **三栏结构**：

```text
┌── 导航栏（后退/前进/向上 + 地址栏 + 搜索）──────────────────┤
├── 导航窗格 ──┬── 文件列表区（带可排序列头）─────────────────┤
├──────────────┴─────────────────────────────────────────┤
├── 状态栏 ──────────────────────────────────────────────┤
```

- 移除右侧 Inspector 面板，详情改为右键菜单 → 属性弹窗
- 移除标题栏下的命令栏（新建/剪切/复制/粘贴/删除/重命名），这些操作已在右键菜单中提供
- 侧栏升级为导航窗格（桌面 + 回收站）
- 列表视图增加可点击排序的列头
- 增加地址栏（可编辑面包屑路径）
- 增加搜索框（当前文件夹内过滤）

---

## 3. 整体布局原型图

### 3.1 列表视图（详细信息 / 默认视图）

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  🔴 🟡 🟢                        📁 文件夹名称 — 文件管理器                     │
├──────────────────────────────────────────────────────────────────────────────┤
│  ←  →  ↑  │  🏠 > Documents > Projects > sub-folder   │  🔍 搜索当前文件夹  │
├────────────┬─────────────────────────────────────────────────────────────────┤
│            │  ┌─    名称 ↑      ┬─  修改日期    ┬─   类型    ┬─   大小  ─┐   │
│  导航窗格   │  ├────────────────┼──────────────┼───────────┼───────────┤   │
│            │  │ 📁 src/         │ 2024-06-01   │ 文件夹     │           │   │
│            │  │ 📁 dist/        │ 2024-06-01   │ 文件夹     │           │   │
│  🏠 桌面 ◀  │  │ 📁 assets/      │ 2024-05-30   │ 文件夹     │           │   │
│            │  │ 📁 docs/        │ 2024-05-28   │ 文件夹     │           │   │
│  🗑 回收站  │  │                │              │           │           │   │
│            │  │ 📄 readme.md   │ 2024-06-01   │ MD 文件    │  2.1 KB   │   │
│            │  │ 📄 config.json │ 2024-06-01   │ JSON 文件  │  0.8 KB   │   │
│            │  │ 📄 index.ts    │ 2024-05-31   │ TS 文件    │  4.5 KB   │   │
│            │  │ 📄 style.css   │ 2024-05-30   │ CSS 文件   │  1.3 KB   │   │
│            │  │                │              │           │           │   │
│            │  └────────────────┴──────────────┴───────────┴───────────┘   │
├────────────┴─────────────────────────────────────────────────────────────────┤
│  ■ 8 个项目  │  已选择 1 个项目 (4.5 KB)          │  ▦ 列表 │ ▤ 小图标 │ ▧ │
└─────────────────────────────────────────────────────────────────────────────┘
```

列表视图特点：
- 一行一个文件/文件夹，信息密度高
- 列头（名称、修改日期、类型、大小）可点击排序（升序/降序切换）
- 文件夹始终排在最前，然后是按当前排序列排列的文件
- 整行选中高亮
- 双击文件夹进入，双击文件用关联应用打开

### 3.2 图标视图（Grid 网格视图）

图标视图分两种尺寸：

**小图标（48px）**：

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  🔴 🟡 🟢                        📁 文件夹名称 — 文件管理器                     │
├──────────────────────────────────────────────────────────────────────────────┤
│  ←  →  ↑  │  🏠 > Documents > Projects   │  🔍 搜索                       │
├────────────┬─────────────────────────────────────────────────────────────────┤
│            │                                                                  │
│  导航窗格   │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────┐ │
│            │  │   📁     │ │   📁     │ │   📁     │ │   📁     │ │  📁  │ │
│  (同上)    │  │  src     │ │  dist    │ │ assets   │ │  docs    │ │ ...  │ │
│            │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────┘ │
│            │                                                                  │
│            │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐          │
│            │  │   📄     │ │   📄     │ │   📄     │ │   📄     │          │
│            │  │ readme   │ │ config   │ │ index    │ │ style    │          │
│            │  │  .md     │ │  .json   │ │  .ts     │ │  .css    │          │
│            │  └──────────┘ └──────────┘ └──────────┘ └──────────┘          │
│            │                                                                  │
├────────────┴─────────────────────────────────────────────────────────────────┤
│  ■ 8 个项目                                     │  ▦ 列表 │ ▤ 小图标 │ ▧    │
└─────────────────────────────────────────────────────────────────────────────┘
```

**大图标（72px）**：布局相同，图标和文字更大。

图标视图特点：
- 网格排列，自适应列数（根据容器宽度 `auto-fill`）
- 只显示图标 + 名称，不显示日期/大小/类型
- 名称支持两行截断
- 适合浏览图片、缩略图等视觉文件

---

## 4. 组件划分

### 新组件树

```text
frontend/src/platform/components/apps/desktop/
├── index.vue                            ← 重构：三栏主布局
└── file-manager/
    ├── fm-navigation-bar.vue            ← 新增：导航栏（后退/前进/向上 + 地址栏 + 搜索）
    ├── fm-nav-pane.vue                  ← 重构自 file-manager-sidebar.vue，升级为导航窗格
    ├── fm-file-list.vue                 ← 重构自 file-manager-content.vue，增加列头+排序
    ├── fm-status-bar.vue                ← 新增：状态栏（项目统计 + 视图切换）
    ├── fm-properties-dialog.vue         ← 新增：属性弹窗（替代原 inspector 面板）
    ├── use-file-manager-state.ts        ← 扩展：增加排序、搜索过滤、视图切换逻辑
    └── types.ts                         ← 扩展：增加排序列、排序方向等类型
```

### 组件对照

| 旧组件 | 新组件 | 变动 |
|--------|--------|------|
| `file-manager-header.vue` | `fm-navigation-bar.vue` | 重构为导航栏（后退/前进/向上 + 地址栏 + 搜索）；移除操作按钮（已由右键菜单覆盖） |
| `file-manager-sidebar.vue` | `fm-nav-pane.vue` | 重构为导航窗格 |
| `file-manager-content.vue` | `fm-file-list.vue` | 增加列头 + 排序 |
| `file-manager-inspector.vue` | `fm-properties-dialog.vue` | 从常驻面板改为弹窗 |
| （无） | `fm-status-bar.vue` | 新增 |

---

## 5. 交互细节

### 5.1 地址栏

```
←  →  ↑  │  🏠 > Documents > Projects > sub-folder   │  🔍
```

- **← 后退 / → 前进**：浏览器式导航历史
- **↑ 向上**：跳转到父文件夹
- **🏠**：快捷回到桌面根目录
- **面包屑路径**：每段可点击跳转，段之间 `>` 分隔
- **点击空白区域**：面包屑变为可编辑文本输入框，支持直接输入路径或复制当前路径
- **搜索框**：输入即实时过滤当前文件夹内容（前端过滤，不需要后端搜索接口）

### 5.2 列头排序

```
┌─    名称 ↑      ┬─  修改日期    ┬─   类型    ┬─   大小  ─┐
```

- 默认按"文件夹优先 + 名称升序"排列
- 点击列头切换排序：
  - 首次点击该列：升序（↑）
  - 再次点击：降序（↓）
  - 点击第三列：回到默认排序
- 当前排序列高亮显示
- 排序规则：
  - 名称：按字符串比较（不区分大小写）
  - 修改日期：按时间戳
  - 类型：按扩展名字符串
  - 大小：按字节数

### 5.3 导航窗格

```
  🏠 桌面          ← 当前打开则高亮
  🗑 回收站        ← 点击打开回收站窗口
```

- 默认仅两个入口：桌面 + 回收站
- 当前打开的文件夹高亮
- 后续可扩展为树形展开（点击文件夹展开子文件夹列表）

### 5.4 右键菜单

保留现有右键菜单逻辑，增加以下入口：
- **属性**：打开属性弹窗（替代原 inspector 面板）

### 5.5 属性弹窗

```
┌─────────────────────────────────┐
│  📁 src 属性                    │
├─────────────────────────────────┤
│  名称：    src                  │
│  类型：    文件夹               │
│  路径：    /Desktop/Projects/   │
│  包含：    5 个文件, 2 个文件夹 │
│  创建时间：2024-01-15 10:30     │
│  修改时间：2024-06-01 14:22     │
├─────────────────────────────────┤
│              [ 确定 ] [ 取消 ]  │
└─────────────────────────────────┘
```

- 通过右键菜单 → 属性 打开
- 模态弹窗，显示文件/文件夹详细信息
- 替代原 Inspector 面板的所有信息展示功能

### 5.6 搜索过滤

- 搜索框在地址栏右侧
- 输入即实时过滤当前文件列表（前端 `computed` 过滤，无需请求后端）
- 匹配规则：文件名包含搜索关键字（不区分大小写）
- 清空搜索框恢复完整列表
- 搜索时状态栏显示"找到 N 个结果"

---

## 6. 状态管理扩展

在现有 `use-file-manager-state.ts` 基础上增加：

### 6.1 新增状态

```typescript
// 新增状态
const sortColumn = ref<'name' | 'date' | 'type' | 'size'>('name')
const sortDirection = ref<'asc' | 'desc'>('asc')
const searchKeyword = ref('')
const navigationHistory = ref<number[]>([])  // 导航历史（文件夹 ID 栈）
const historyIndex = ref(-1)                  // 当前在历史中的位置

// 新增计算属性
const filteredItems = computed(() => {
  // 先按搜索关键词过滤文件名
  // 再按 sortColumn + sortDirection 排序
  // 文件夹始终排前
})

const canGoBack = computed(() => historyIndex.value > 0)
const canGoForward = computed(() => historyIndex.value < navigationHistory.value.length - 1)
```

### 6.2 状态重置规则（P3）

**关键前提**：`options.folderId` 是从 props 传入的只读 getter（`() => props.folderId`），只在窗口 payload 变化时触发。而 `openItem` / `goBack` / `goForward` / `goUp` / `navigateToCrumb` / `goRoot` 全部直接操作内部 ref `currentFolderId`，完全绕过 props。

`watch(options.folderId, ...)` 仅在以下场景触发：
- **singleton 模式**：桌面双击另一文件夹 → `updateWindowPayload` 更新 payload.folderId
- **allowMultiple 模式**：仅在窗口首次创建时触发一次（之后 payload 不再变化）

因此，reset 规则**不能只挂在 props watcher 上**，必须抽一个统一的内部函数 `enterFolder(folderId: number)`，所有导航路径都调用它。

```typescript
/**
 * 所有进入新文件夹的操作（openItem / goBack / goForward /
 * goUp / navigateToCrumb / goRoot）统一走此函数。
 * 保证 sortColumn / searchKeyword 等状态在所有导航路径上都正确重置。
 */
function enterFolder(folderId: number) {
  // 重置浏览状态
  sortColumn.value = 'name'
  sortDirection.value = 'asc'
  searchKeyword.value = ''
  selectedId.value = null

  // 应用目标文件夹
  currentFolderId.value = folderId
  void loadFiles()
}
```

各导航路径改为：

```typescript
function openItem(item: FileEntry) {
  if (item.is_folder) {
    // 截断当前位置之后的历史，追加新节点
    navigationHistory.value = navigationHistory.value.slice(0, historyIndex.value + 1)
    navigationHistory.value.push(item.id)
    historyIndex.value++

    breadcrumb.value.push({ id: item.id, name: item.file_name })
    enterFolder(item.id)
    return
  }
  openFileByRecord({ fileId: item.id, fileName: displayName(item), format: item.format || '' })
}

function goBack() {
  if (!canGoBack.value) return
  historyIndex.value--
  const targetId = navigationHistory.value[historyIndex.value]
  // 重建 breadcrumb（调用后端 path API 或用缓存）
  enterFolder(targetId)
}

function goForward() {
  if (!canGoForward.value) return
  historyIndex.value++
  const targetId = navigationHistory.value[historyIndex.value]
  enterFolder(targetId)
}

function goUp() {
  if (!canGoUp.value) return
  breadcrumb.value.pop()
  const parent = breadcrumb.value[breadcrumb.value.length - 1]
  enterFolder(parent.id ?? 0)
}

function navigateToCrumb(index: number) {
  const crumb = breadcrumb.value[index]
  breadcrumb.value = breadcrumb.value.slice(0, index + 1)
  enterFolder(crumb.id ?? 0)
}

function goRoot() {
  currentFolderId.value = 0
  breadcrumb.value = [{ id: null, name: '桌面' }]
  enterFolder(0)
}
```

`watch(options.folderId, ...)` 保留，但只用于**窗口首次创建 / payload 被外部更新时**的场景：

```typescript
// 仅在窗口被外部指定新 folderId 时触发（singleton 复用 / 初始加载）
watch(options.folderId, (newId) => {
  if (newId !== undefined) {
    applyInitialFolder()       // 初始化 breadcrumb
    enterFolder(Number(newId)) // 统一走 enterFolder，重置规则生效
  }
})
```

| 状态 | 进入新文件夹时的行为（`enterFolder` 内） | 理由 |
|------|------|------|
| `sortColumn` | **重置**为 `'name'` | 不同文件夹的文件集不同，保留旧排序没有意义 |
| `sortDirection` | **重置**为 `'asc'` | 同上 |
| `searchKeyword` | **清空**为 `''` | 搜索是针对"当前文件夹"的，切出去时应清空 |
| `selectedId` | **清空**为 `null` | 已有此逻辑，保持一致 |
| `navigationHistory` | **不在 enterFolder 中操作** | 入栈/出栈逻辑在各自调用方（openItem/goBack/goForward）中已完成 |

### 6.3 refresh:file-list 事件监听（P4，可选）

```typescript
import { onMounted, onUnmounted } from 'vue'
import { useDesktopEventBus } from '@/desktop/events/use-desktop-event-bus'

const { on, off } = useDesktopEventBus()

function onFileRefresh(d?: unknown) {
  const payload = d as Record<string, unknown> | undefined
  const id = payload?.folderId as number | undefined
  if (id !== undefined && id === currentFolderId.value) {
    void loadFiles()
  }
}

onMounted(() => { on('refresh:file-list', onFileRefresh) })
onUnmounted(() => { off('refresh:file-list', onFileRefresh) })
```

---

## 7. 前置依赖：多实例基础设施修复

当前 desktop 应用为 singleton（`allowMultiple: false`），整个文件管理器只有一个 Vue 组件实例。重构方案中的"后退/前进/历史导航"在同一窗口内切换文件夹时会互相覆盖，没有意义；排序/搜索的状态也需要每个窗口独立。

因此，在开始 UI 重构前，必须先完成多实例基础设施。

### P0：sidebar 折叠状态从模块共享迁移为窗口级独立

`frontend/src/desktop/window-manager/use-desktop-layout-state.ts` 中：

```typescript
const sidebarCollapsed = ref(false)   // ← 模块作用域！所有 desktop 窗口共享
```

该文件**仅此一个模块级 ref，无其他共享字段**。当前 singleton 时无问题，但开启 allowMultiple 后，A 窗口折叠 sidebar 会连带影响 B 窗口。

**但问题不止多窗口隔离**。当前架构存在一个更基础的通信断层：

- `useDesktopLayoutState()` **仅在** `desktop-window-frame.vue:117` 一处调用
- 折叠按钮渲染在 `desktop-window-frame.vue` 的标题栏（第 19 行）
- sidebar 组件 `<FileManagerSidebar>` 渲染在 `apps/desktop/index.vue`（第 17 行）——**这是 window-frame 的子组件**，通过 `<component :is="currentComponent" v-bind="payload || {}" />` 嵌入
- 子组件**没有**调用 `useDesktopLayoutState()`，payload 里也不含 `sidebarCollapsed`
- 当前 `<FileManagerSidebar>` 模板里没有任何 `v-if` / `v-show` 绑定 sidebar 折叠状态

**结论**：`sidebarCollapsed` 是一个被按钮 toggled 但从未被 sidebar 消费的状态，sidebar 折叠功能本身就是未接线的。之前靠模块级 ref 实现了"按钮有自己的视觉反馈"（`is-collapsed` / `is-open` CSS），但 sidebar 显隐从未生效。

**修复方案（两步）**：

**第一步**：将 ref 移入函数体，每个窗口独立：

```typescript
export function useDesktopLayoutState() {
  const sidebarCollapsed = ref(false)   // ← 移入函数体，每窗口独立
  function toggleSidebar() { sidebarCollapsed.value = !sidebarCollapsed.value }
  function setSidebarCollapsed(v: boolean) { sidebarCollapsed.value = v }
  return {
    sidebarCollapsed: computed(() => sidebarCollapsed.value),
    toggleSidebar,
    setSidebarCollapsed,
  }
}
```

**第二步**：用 `provide` / `inject` 将状态从 `desktop-window-frame.vue` 传递到子组件 `apps/desktop/index.vue`。不能单纯依赖模块级单例"隐式共享"——ref 移入函数体后这个机制就断了。

```typescript
// desktop-window-frame.vue
import { provide } from 'vue'
const layoutState = useDesktopLayoutState()
provide('desktopLayoutState', layoutState)

// apps/desktop/index.vue
import { inject } from 'vue'
const layoutState = inject('desktopLayoutState')
// <FileManagerSidebar v-show="!layoutState?.sidebarCollapsed.value" />
```

**影响范围**：`use-desktop-layout-state.ts`（移 ref）+ `desktop-window-frame.vue`（加 provide）+ `apps/desktop/index.vue`（加 inject + v-show）。

### P1：修复 `restoreWindows` 的去重逻辑

`frontend/src/desktop/window-manager/window-manager.ts:167-171`：

```typescript
for (const w of restoredWindows) {
  const existingWindow = windows.find(
    x => x.appKey === w.appKey && x.minimized === w.minimized
  )
  if (existingWindow) { activateWindow(existingWindow.id); continue }
  windows.push(w)
}
```

**`minimized` 条件的来由**：对于 singleton app，如果保存了两个快照（一个 minimized=true、一个 minimized=false），它们应被视为两个不同状态分别恢复。`minimized` 条件确保这两者不会互相去重。

**当前不触发是因为 `restoreWindows` 只在启动时调用一次（`windows` 为空）。一旦允许多个 desktop 窗口，刷新页面后如果有两个同 minimized 状态的 desktop 快照，`find()` 只返回第一个 → 第二个静默丢失，无任何报错。**

**修复方案**：保留 `minimized` 条件对 singleton app 的保护，对 `allowMultiple: true` 的 app 跳过去重：

```typescript
for (const w of restoredWindows) {
  const app = getApp(w.appKey)
  if (app && !app.allowMultiple) {
    const existingWindow = windows.find(
      x => x.appKey === w.appKey && x.minimized === w.minimized
    )
    if (existingWindow) { activateWindow(existingWindow.id); continue }
  }
  windows.push(w)
}
```

**影响范围**：`window-manager.ts` 一处。需引入 `getApp`（已 import）。

### P2：开启 allowMultiple

`backend/app/seed_data/apps.json` 中 desktop 记录：

```json
"singleton": true,
```

改为 `false`，或增加 `"allow_multiple": true`。前端 `app-loader.ts:65` 已支持 `allow_multiple` 字段读取。

**P0、P1 必须在本步之前完成。** 缺少任何一步都会导致可复现的 UI bug。

### P3：明确状态重置规则

**关键问题**：`options.folderId` 是从 props 传入的只读 getter（`() => props.folderId`），只在窗口 payload 变化时触发。`openItem` / `goBack` / `goForward` / `goUp` / `navigateToCrumb` 全部操作内部 ref `currentFolderId`，完全绕过 props。如果 reset 规则只挂在 `watch(options.folderId)` 里，打开 allowMultiple 后只在窗口初始化时执行一次，日常导航路径全部不触发。

**修正方案**：抽统一函数 `enterFolder(folderId: number)`，所有导航路径（包括 props watcher）都调用它。详见上文 6.2 节。

### P4（可选）：refresh:file-list 事件监听

`use-file-manager-state.ts` 中增加监听，当收到 `refresh:file-list` 事件且 `payload.folderId === currentFolderId.value` 时自动刷新当前列表。低成本解决两个窗口打开同一文件夹时的弱一致性问题。

---

## 8. UI 组件开发（Step 1–9）

以下步骤与 P0–P4 正交，可并行开发。

| 步骤 | 内容 | 涉及文件 |
|------|------|----------|
| Step 1 | 创建 `fm-navigation-bar.vue`（后退/前进/向上 + 地址栏 + 搜索） | 新增 |
| Step 2 | 重构 `file-manager-sidebar.vue` → `fm-nav-pane.vue`（简化导航：桌面+回收站） | 重构 |
| Step 3 | 重构 `file-manager-content.vue` → `fm-file-list.vue`（增加列头+排序） | 重构 |
| Step 4 | 创建 `fm-status-bar.vue`（状态栏 + 视图切换） | 新增 |
| Step 5 | 创建 `fm-properties-dialog.vue`（属性弹窗） | 新增 |
| Step 6 | 重构 `index.vue`（整合新组件、移除 inspector、移除旧 header） | 重构 |
| Step 7 | 扩展 `use-file-manager-state.ts`（排序、搜索、历史导航 + P4 事件监听） | 扩展 |
| Step 8 | 删除旧 `file-manager-inspector.vue` | 删除 |
| Step 9 | 统一样式调整 + 自测 | CSS |

---

## 9. 移出本文档的事项

- **红绿灯窗口按钮**（Step 0）：影响 `desktop-window-frame.vue` 所有窗口（desktop / notepad / calculator / panel 等 10+ 个窗口），不是文件管理器专属改动，单独立项评估。测试范围需覆盖 desktop + notepad + calculator + 一个 panel 类型窗口。

---

## 10. 不做的事项

- ❌ 不在此阶段实现"此电脑"虚拟磁盘节点（导航窗格仅保留桌面 + 回收站）
- ❌ 不实现文件多选（复选框或 Ctrl+Click），当前为单选模式
- ❌ 不实现拖拽移动文件到导航窗格文件夹（后续迭代）
