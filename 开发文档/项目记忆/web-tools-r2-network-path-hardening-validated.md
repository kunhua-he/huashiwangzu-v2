---
name: "web-tools r2 network path hardening validated"
type: "task"
tags: [web-tools, r2, network, ssrf, proxy, validation]
agent: "codex-conductor-sweep-20260703-r2"
created: "2026-07-03T09:32:37.604917+00:00"
---

# 改了什么

主会话接管 web-tools r2 审计遗留：

- `WEB_TOOLS_PROXY` 改为显式可选；未配置时直连，不再默认硬编码 `127.0.0.1:4780`。
- search/fetch 统一使用代理候选：配置代理时先代理失败后直连；未配置只直连。
- httpx client 增加 `trust_env=False`，避免系统代理环境污染工具结果。
- fetch HEAD 响应显式 `aclose()`；GET 流式响应仍 finally 关闭。
- fetch 对空正文返回结构化失败，避免空内容假成功；search 对 provider 返回全被过滤时返回结构化失败。
- sandbox 从纯复制契约升级为导入生产 router helper，覆盖直接网络默认、success:false 响应拒绝、内容类型/解码守卫。
- `.gitignore` 增加根 `data/uploads/`，防止运行时上传文件继续污染工作区；不删除现有上传文件。

# 验证了什么

- `ruff`: `modules/web-tools/backend/router.py`、`modules/web-tools/sandbox/test_module.py` 全通过。
- `run_test`: `modules/web-tools/sandbox/test_module.py` 12 passed。
- 后端重启后 `/api/health` 200，`module_errors=null`；`/api/web-tools/health` 200。
- 活栈：`web-tools:fetch` 访问 `127.0.0.1` 返回 422 SSRF；空 URL 返回 422；`https://example.com` 返回 200 且有 title/text。
- `tail_log` 无新增错误。
- `git check-ignore -v data/uploads/...` 命中 `.gitignore:data/uploads/`。

# 残留风险

web-tools 真实搜索依赖外部网络和 ddgs provider，未在本次提交里强打真实搜索；后续可由网络工具专项继续覆盖 search provider 空结果和速率限制。
