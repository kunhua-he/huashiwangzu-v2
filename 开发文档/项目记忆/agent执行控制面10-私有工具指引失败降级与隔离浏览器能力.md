---
name: "Agent执行控制面10-私有工具指引失败降级与隔离浏览器能力"
type: task
tags: ["agent", "tool-guidance", "degradation", "browser-tools", "execution-control"]
created: 2026-06-30
agent: opencode
---

## 做了什么

实现了三大目标：
1. **私有工具指引控制面** — 3 张新表（agent_tool_guides/versions/candidates）+ 8 个能力 + 10 HTTP 端点，支持版本化/禁用/回滚/候选晋升/合并顺序渲染
2. **失败分类与降级** — 13 种错误分类 + 5 条初始降级 recipe（publish、git clone、syntax、URL 跳转、tool discovery）
3. **隔离 browser-tools 模块** — Playwright 沙箱隔离，9 个能力，安全边界（URL 过滤、无 Cookie 暴露、大小限制）

## 改了哪些

- 新增：tool_guidance_service.py, handlers/tool_guidance.py, test_tool_guidance.py, browser-tools 模块（manifest/router/handlers）
- 修改：models.py, init_db.py, bootstrap.py, router.py（agent 模块）

## 踩过的坑

- classify_and_degrade 能力仅在 bootstrap.py 注册但 bootstrap 不自动执行，需在 handlers/tool_guidance.py 加 register_capability
- Playwright 依赖需在前端 venv 中安装（通过 symlink 解决）
- async 测试 mock 的 `.scalars().all()` / `.scalar_one_or_none()` 层级易用错

## 遗留问题

见交付剩余风险.md，主要：Runtime 自动注入需下次迭代，Playwright 环境依赖（已配置），测试数据有一条 disabled 记录未清理。

