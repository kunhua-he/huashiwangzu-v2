# 执行信：桌面视觉通知中心与 Fluent 质感增强

## 目标

只做桌面视觉体验增强：通知中心、任务栏反馈、卡片层级、阴影、空态、动效过渡，让当前已经可操作的反馈中心更像成熟桌面工作台。

## 修改边界

只允许：

```text
frontend/src/desktop/taskbar/
frontend/src/shared/components/notification-panel.vue
frontend/src/shared/components/load-state-banner.vue
frontend/src/desktop/shell/ 与视觉样式直接相关文件
frontend/src/styles/ 或已有全局样式文件
frontend/tests/ 视觉/交互最小测试
开发文档/项目记忆/
```

禁止：

```text
backend/
dev_toolkit/
modules/agent/backend/
modules/knowledge/backend/
frontend/src/shared/api/
frontend/src/shared/files/
```

## 必做

1. 通知中心视觉分层：主反馈、任务、Agent、Knowledge、错误/债务分类更清楚。
2. Fluent 风格：圆角、阴影、hover、focus、轻微过渡。
3. 空态/错误态/加载态视觉统一。
4. 不改业务逻辑，不改 API 契约。
5. 保持键盘可达和基本可访问性。

## 验收

```bash
cd frontend && npm run build
```

目标文件扫描：

```text
无 any/as any/@ts-ignore/@ts-expect-error
```

如可行补 Playwright 最小截图/可见性测试；否则报告写明手工验证路径。

## 交付

写：

```text
开发文档/项目记忆/桌面视觉通知中心与Fluent质感增强收口.md
```

调用：

```text
finish_task(...)
memory_write(agent="codex-desktop-visual-fluent-r1")
mcp_feedback(agent="codex-desktop-visual-fluent-r1")
```

## 提示词

请读取并执行：‘/Users/hekunhua/Documents/Agent/PHP/华世王镞_v2/开发文档/项目记忆/执行信-桌面视觉通知中心与Fluent质感增强.md’
