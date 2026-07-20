# 访达深度审计报告 + 修复计划（无效点击 / 显示异常 / 链路异常）

## 审计范围
- 访达窗内：工具栏 / 侧栏 / 空白与条目右键 / 快捷键 / 列表·分栏·画廊
- 桌面壳：桌面图标右键、拖放冲突
- 窗口 Tabs、标签自定义、撤销

**方法**：菜单 key 与 handler 全量对照 + 关键路径读码（子代理限流后改为直接扫码）。

---

## 一、确认「点了没反应 / 行为错」的问题（按严重度）

### P0 — 用户会明确感觉坏掉

| # | 入口 | 现象 | 根因证据 | 建议修复 |
|---|---|---|---|---|
| 1 | 文件夹右键 **「上传到此处」** | 文件仍上传到**当前打开目录**，不是右键目标夹 | `fm-file-operations.ts`：`upload-here` → `triggerUpload()` → `uploadFile(..., currentFolderId)`；对比桌面壳 `triggerUpload(file.id)` 是对的 | 增加 `pendingUploadFolderId`；`upload-here` 设为 `file.id`，上传后清空 |
| 2 | 文件夹右键 **「在此处新建文件夹」** | 新文件夹建在**当前目录**，不是目标夹 | `create-folder-here` → `createFolder()` 固定 `currentFolderId` | `createFolder(parentId?)`，here 时传 `file.id` |
| 3 | 文件夹右键 **「新建文件」子菜单** | 同样建在当前目录 | `createFileFromMenuKey` 只用 `currentFolderId` | 同上，带目标 `folderId` |
| 4 | 访达窗 **Tabs** | 多标签后，在某一标签内导航会**污染其它标签标题/路径**（像坏了） | `desktop-window-frame.vue` watch `payload.folderId/folderName` 写回 **active tab**；但组件实例切换时 payload 与 tab 状态未隔离好；新建 tab 后导航仍走同一 window payload | 导航时只更新 active tab 的 folderId/title；`updateWindowPayload` 与 tab 双向同步时禁止覆盖非 active tab；或每个 tab 独立 state key |
| 5 | 粘贴 **撤销 ⌘Z（剪切粘贴）** | 可能撤错位置 | `paste-here` 时 `fromFolder = currentFolderId`，不是剪贴板项真实来源 | 剪贴时把 `sourceFolderId` 写入 clipboard item；undo 用该字段 |

### P1 — 点了静默无反馈 / 半残

| # | 入口 | 现象 | 根因 | 建议 |
|---|---|---|---|---|
| 6 | 桌面空白右键 **查看/排序方式**（`view-list` `sort-name`…） | 点了无效果 | `desktop-shell-context-menu` / `buildDesktopBlankMenu` 声明了 key；`shell/index.vue` `handleContextMenuSelect` **无分支** | 接上桌面图标布局/排序，或从菜单移除避免假按钮 |
| 7 | 桌面图标右键缺 **制作副本/压缩/解压/标签** | 访达里有、桌面没有 | shell handler 只处理 open/download/cut/copy/rename/delete… | 与访达对齐关键套动作，或明确桌面菜单收敛 |
| 8 | 剪切/复制（访达内） | 常无 toast | `cutItems/copyItems` 后无 `feedback.success` | 统一成功提示 |
| 9 | 侧栏标签 **「编辑」自定义名** | 部分环境 textarea 交互异常 | `ElMessageBox.prompt` + `inputType: 'textarea'` 兼容性不稳 | 改为逐色 prompt 或自研小对话框 |
| 10 | 工具栏传入 `canGoUp` / `@go-up` | **UI 无「上层」按钮**（Backspace 能用） | `fm-navigation-bar` 只画后退/前进，未画 go-up | 加「上层」按钮或去掉无用 prop 避免误导 |

### P2 — 显示/体验异常（非完全死按钮）

| # | 问题 | 证据/说明 |
|---|---|---|
| 11 | 标签菜单仍用静态 `FINDER_TAGS` 名，侧栏自定义名**不同步到右键标签** | `buildTagMenuChildren` 用 `FINDER_TAGS`，未用 `listTagsWithCustomNames()` |
| 12 | 新建标签页永远 `folderId:0 桌面`，无法「复制当前路径为新标签」 | `addFinderTab` 写死桌面 |
| 13 | 状态栏 `update:viewMode` emit 无 UI 触发 | 死代码，无害 |
| 14 | 压缩下载文件名固定「归档.zip」 | blob 拦截器丢 Content-Disposition |
| 15 | 真 OS vibrancy / iCloud | 产品边界，非 bug |

### 已核对「正常」的部分（避免误报）
- 工具栏：上传/新建/刷新/路径栏/预览/四视图/搜索范围 — 均有 emit + 父监听
- 侧栏：桌面/文稿/下载/回收站/标签筛选 — 有接线
- 路径栏 navigate — 有
- 条目菜单：open / download / cut / copy / duplicate / compress / decompress(zip) / tags / details / rename / delete / open-in-new-window — handler 存在
- 空白：upload / create-folder / refresh / paste / group-by — 存在
- 快捷键 ⌘[ ] C X V D I F O W Z — 有实现

---

## 二、修复计划（一次整批，不挤牙膏）

### 批次 A — 目标目录语义（P0 1–3）
1. `fm-file-operations` 增加 `pendingTargetFolderId`
2. `upload-here` / `create-folder-here` / `create-file:*`（当 ctxt 为文件夹）写入目标 id
3. `onUploadFile` / `createFolder` / `createFileFromMenuKey` 读 pending，完成后清空
4. 单测/手测：在 A 夹打开时，对 B 夹右键上传/新建 → 落在 B

### 批次 B — Tabs 隔离（P0 4）
1. 导航 `syncWindowTitle` / `updateWindowPayload` 时同步 **仅 active tab**
2. 切换 tab 时用 tab 自己的 folderId 驱动子组件 key（已有 key，强化 seed）
3. 「+」新标签：可选「当前路径副本」vs 桌面（默认当前路径更 Finder）
4. 关闭 active tab 切到相邻 tab 并恢复其 folder

### 批次 C — 撤销正确性（P0 5）
1. clipboard item 增加 `sourceFolderId?`
2. cut/copy 时写入 `currentFolderId`
3. paste undo 用 clip 的 source，而不是粘贴时的 current

### 批次 D — 死菜单与反馈（P1）
1. 桌面空白：实现 sort/view **或删除**假菜单项（推荐实现最小：排序只影响桌面图标排序状态）
2. 访达 cut/copy 成功 toast
3. 工具栏增加「上层」按钮
4. 标签自定义：避免 textarea prompt；右键标签名用自定义名

### 批次 E — 显示一致性
1. `buildTagMenuChildren` → `listTagsWithCustomNames()`
2. 压缩文件名：从 zip 项推导更好默认名

---

## 三、验收清单（修完必须勾）
- [ ] 右键文件夹「上传到此处」文件出现在该夹
- [ ] 「在此处新建文件夹/文件」落在该夹
- [ ] 两标签分别进入不同目录，互不串标题
- [ ] 剪切从 A 到 B 后 ⌘Z 回到 A
- [ ] 无「点了完全没反应」的右键项（禁用或已实现）
- [ ] 侧栏自定义标签名与右键标签一致
- [ ] vue-tsc；只提交访达相关；ff main

---

## 四、明确不修（边界）
- iCloud / 网络宗卷 / 系统级 vibrancy
- 桌面与访达 100% 同一套菜单（若选「收敛桌面菜单」则文档说明）

---

**批准后按 A→B→C→D→E 同一轮改完并推送，不再拆成多日挤牙膏。**
